using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace DotNetAgent
{
    internal class RunningCommandsManager
    {
        private static Dictionary<uint, RunningCommandInfo> _runningCommands = new Dictionary<uint, RunningCommandInfo>();
        private static readonly object _runningLock = new object();

        private const byte PLUGIN_STOP_TLV = 0x3F;
        private const byte TLV_COMMAND_DATA = 0x39;
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateProcess(IntPtr hProcess, uint uExitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint GetProcessId(IntPtr hProcess);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr CreateToolhelp32Snapshot(uint dwFlags, uint th32ProcessID);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool Process32First(IntPtr hSnapshot, ref PROCESSENTRY32 lppe);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool Process32Next(IntPtr hSnapshot, ref PROCESSENTRY32 lppe);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, uint dwProcessId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);

        private const uint TH32CS_SNAPPROCESS = 0x00000002;
        private const uint PROCESS_TERMINATE = 0x0001;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        private struct PROCESSENTRY32
        {
            public uint dwSize;
            public uint cntUsage;
            public uint th32ProcessID;
            public IntPtr th32DefaultHeapID;
            public uint th32ModuleID;
            public uint cntThreads;
            public uint th32ParentProcessID;
            public int pcPriClassBase;
            public uint dwFlags;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
            public string szExeFile;
        }

        internal class RunningCommandInfo
        {
            public Thread Thread;
            public NamedPipeCommunication Pipe;
            public IntPtr ProcessHandle;
            public uint MaxStopTime = 5;
            public bool IsPlugin;

        }

        public static void RegisterCommand(uint id, RunningCommandInfo info)
        {
            lock (_runningLock)
            {
                _runningCommands[id] = info;
            }
        }

        public static void UnregisterCommand(uint id)
        {
            lock (_runningLock)
            {
                _runningCommands.Remove(id);
            }
        }

        public static List<uint> GetRunningCommands()
        {
            lock (_runningLock)
            {
                return _runningCommands.Keys.ToList();
            }
        }

        public static bool SendCommandData(uint id, byte[] data)
        {
            lock (_runningLock)
            {
                RunningCommandInfo info;
                if (!_runningCommands.TryGetValue(id, out info) || info?.Pipe == null)
                    return false;
                TLV tlv = new TLV(TLV_COMMAND_DATA, data);
                return info.Pipe.Send(tlv.GetFullBuffer());
            }
        }

public static void SetCommandProcessHandle(uint id, IntPtr processHandle)
        {
            lock (_runningLock)
            {
                RunningCommandInfo info;
                if (_runningCommands.TryGetValue(id, out info))
                    info.ProcessHandle = processHandle;
            }
        }

        public static void UpdateCommandMaxStopTime(uint id, uint maxStopTime)
        {
            lock (_runningLock)
            {
                RunningCommandInfo info;
                if (_runningCommands.TryGetValue(id, out info))
                    info.MaxStopTime = maxStopTime;
            }
        }

        public static void StopCommand(uint id)
        {
            RunningCommandInfo info;
            lock (_runningLock)
            {
                if (!_runningCommands.TryGetValue(id, out info))
                    return;
                // Command is removed before stop operations. This prevents double-stop
                // races where concurrent StopCommand calls could both try to terminate
                // the same process. Trade-off: if stop fails, the command cannot be retried.
                _runningCommands.Remove(id);
            }

            if (info.IsPlugin)
                StopPluginCommand(id, info);
            else
                StopNativeCommand(id, info);
        }

        private static void StopPluginCommand(uint id, RunningCommandInfo info)
        {
            if (info.Pipe != null)
            {
                TLV stopTlv = new TLV(PLUGIN_STOP_TLV);
                info.Pipe.Send(stopTlv.GetFullBuffer());

                if (info.Thread != null && info.Thread.IsAlive)
                    info.Thread.Join((int)(info.MaxStopTime * 1000));
            }

            if (info.Thread != null && info.Thread.IsAlive)
            {
                Logger.Warning("Plugin command thread still alive after graceful stop attempt");
                MessagesManager.NewResult(id, null, MessagesManager.CommandStatus.FAILED,
                    Encoding.UTF8.GetBytes("Was not able to stop actually but not receiving more data also"));
            }
        }

        private static void StopNativeCommand(uint id, RunningCommandInfo info)
        {
            Logger.Info("Stopping native command");
            if (info.ProcessHandle != IntPtr.Zero)
            {
                uint pid = GetProcessId(info.ProcessHandle);
                if (pid != 0)
                {
                    Logger.Info("Terminating process tree for PID " + pid);
                    KillProcessTree(pid);
                }
                else
                {
                    Logger.Info("Terminating process (could not get PID for tree kill)");
                    TerminateProcess(info.ProcessHandle, 1);
                }
            }
        }

        private static void KillProcessTree(uint pid)
        {
            List<uint> children = GetChildProcessIds(pid);
            foreach (uint childPid in children)
            {
                KillProcessTree(childPid);
            }

            IntPtr hProcess = OpenProcess(PROCESS_TERMINATE, false, pid);
            if (hProcess != IntPtr.Zero)
            {
                TerminateProcess(hProcess, 1);
                CloseHandle(hProcess);
            }
        }

        private static List<uint> GetChildProcessIds(uint parentPid)
        {
            List<uint> children = new List<uint>();
            IntPtr snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (snapshot == IntPtr.Zero || snapshot == new IntPtr(-1))
                return children;

            try
            {
                PROCESSENTRY32 entry = new PROCESSENTRY32();
                entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));

                if (Process32First(snapshot, ref entry))
                {
                    do
                    {
                        if (entry.th32ParentProcessID == parentPid)
                            children.Add(entry.th32ProcessID);
                    } while (Process32Next(snapshot, ref entry));
                }
            }
            finally
            {
                CloseHandle(snapshot);
            }

            return children;
        }
    }
}
