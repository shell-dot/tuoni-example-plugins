using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

namespace DotNetAgent
{
    internal static class NativeCommandPsHelper
    {
        private const uint PROCESS_QUERY_INFORMATION = 0x0400;
        private const uint PROCESS_VM_READ = 0x0010;
        private const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
        private const int TOKEN_QUERY = 0x0008;
        private const int TokenUser = 1;
        private const int TokenIntegrityLevel = 25;

        private const int SECURITY_MANDATORY_LOW_RID = 0x1000;
        private const int SECURITY_MANDATORY_MEDIUM_RID = 0x2000;
        private const int SECURITY_MANDATORY_HIGH_RID = 0x3000;
        private const int SECURITY_MANDATORY_SYSTEM_RID = 0x4000;

        private const long FILETIME_TO_UNIX_EPOCH_DIFFERENCE = 116444736000000000L;
        private const long FILETIME_TICKS_PER_SECOND = 10000000L;

        private const byte TLV_PROCESS = 0x1;
        private const byte TLV_PID = 0x1;
        private const byte TLV_NAME = 0x2;
        private const byte TLV_USER = 0x3;
        private const byte TLV_BITNESS = 0x4;
        private const byte TLV_INTEGRITY = 0x5;
        private const byte TLV_PARENT_PID = 0x6;
        private const byte TLV_CREATION_TIME = 0x7;
        private const byte TLV_SESSION_ID = 0x8;

        [StructLayout(LayoutKind.Sequential)]
        private struct PROCESS_BASIC_INFORMATION
        {
            public IntPtr Reserved1;
            public IntPtr PebBaseAddress;
            public IntPtr Reserved2_0;
            public IntPtr Reserved2_1;
            public IntPtr UniqueProcessId;
            public IntPtr InheritedFromUniqueProcessId;
        }

        private enum SID_NAME_USE
        {
            SidTypeUser = 1,
            SidTypeGroup,
            SidTypeDomain,
            SidTypeAlias,
            SidTypeWellKnownGroup,
            SidTypeDeletedAccount,
            SidTypeInvalid,
            SidTypeUnknown,
            SidTypeComputer,
            SidTypeLabel
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SYSTEM_INFO
        {
            public ushort wProcessorArchitecture;
            public ushort wReserved;
            public uint dwPageSize;
            public IntPtr lpMinimumApplicationAddress;
            public IntPtr lpMaximumApplicationAddress;
            public IntPtr dwActiveProcessorMask;
            public uint dwNumberOfProcessors;
            public uint dwProcessorType;
            public uint dwAllocationGranularity;
            public ushort wProcessorLevel;
            public ushort wProcessorRevision;
        }

        private const ushort PROCESSOR_ARCHITECTURE_AMD64 = 9;

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, uint dwProcessId);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool OpenProcessToken(IntPtr ProcessHandle, int DesiredAccess, out IntPtr TokenHandle);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool GetTokenInformation(IntPtr TokenHandle, int TokenInformationClass, IntPtr TokenInformation, int TokenInformationLength, out int ReturnLength);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool LookupAccountSidW(
            string lpSystemName,
            IntPtr Sid,
            StringBuilder lpName,
            ref int cchName,
            StringBuilder lpReferencedDomainName,
            ref int cchReferencedDomainName,
            out SID_NAME_USE peUse);

        [DllImport("advapi32.dll", CharSet = CharSet.Auto)]
        private static extern IntPtr GetSidSubAuthority(IntPtr pSid, uint nSubAuthority);

        [DllImport("advapi32.dll", CharSet = CharSet.Auto)]
        private static extern IntPtr GetSidSubAuthorityCount(IntPtr pSid);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool IsWow64Process(IntPtr hProcess, [MarshalAs(UnmanagedType.Bool)] out bool wow64Process);

        [DllImport("kernel32.dll")]
        private static extern void GetNativeSystemInfo(out SYSTEM_INFO lpSystemInfo);

        [DllImport("ntdll.dll")]
        private static extern int NtQueryInformationProcess(
            IntPtr ProcessHandle,
            int ProcessInformationClass,
            ref PROCESS_BASIC_INFORMATION ProcessInformation,
            int ProcessInformationLength,
            out int ReturnLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetProcessTimes(
            IntPtr hProcess,
            out long lpCreationTime,
            out long lpExitTime,
            out long lpKernelTime,
            out long lpUserTime);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseHandle(IntPtr hObject);

        public static TLV BuildProcessListTlv()
        {
            TLV resultTlv = new TLV(TLV_PROCESS);

            Process[] processes = Process.GetProcesses();
            foreach (Process proc in processes)
            {
                try
                {
                    if (proc.Id == 0)
                        continue;

                    uint pid = (uint)proc.Id;
                    IntPtr hProcess = OpenProcessWithFallback(pid);

                    TLV procTlv = new TLV(TLV_PROCESS);
                    procTlv.AddChild(new TLV(TLV_PID, BitConverter.GetBytes(pid)));
                    procTlv.AddChild(new TLV(TLV_NAME, Encoding.UTF8.GetBytes(GetProcessName(proc))));
                    procTlv.AddChild(new TLV(TLV_USER, Encoding.UTF8.GetBytes(GetProcessUser(hProcess))));
                    procTlv.AddChild(new TLV(TLV_BITNESS, Encoding.UTF8.GetBytes(hProcess == IntPtr.Zero ? "???" : (IsProcess64Bit(hProcess) ? "64bit" : "32bit"))));
                    procTlv.AddChild(new TLV(TLV_INTEGRITY, Encoding.UTF8.GetBytes(GetProcessIntegrityLevel(hProcess))));
                    procTlv.AddChild(new TLV(TLV_PARENT_PID, BitConverter.GetBytes(GetProcessParentPID(hProcess))));
                    procTlv.AddChild(new TLV(TLV_CREATION_TIME, BitConverter.GetBytes(GetProcessCreationTime(hProcess))));
                    procTlv.AddChild(new TLV(TLV_SESSION_ID, BitConverter.GetBytes(GetSessionId(proc))));
                    resultTlv.AddChild(procTlv);

                    if (hProcess != IntPtr.Zero)
                        CloseHandle(hProcess);
                }
                catch (Exception)
                {
                }
                finally
                {
                    proc.Dispose();
                }
            }

            return resultTlv;
        }

        private static IntPtr OpenProcessWithFallback(uint pid)
        {
            IntPtr hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, false, pid);
            if (hProcess == IntPtr.Zero)
                hProcess = OpenProcess(PROCESS_QUERY_INFORMATION, false, pid);
            if (hProcess == IntPtr.Zero)
                hProcess = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid);
            return hProcess;
        }

        private static string GetProcessName(Process proc)
        {
            try
            {
                return proc.ProcessName;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Failed to get process name: {ex.Message}");
                return "???";
            }
        }

        private static string GetProcessUser(IntPtr hProcess)
        {
            if (hProcess == IntPtr.Zero)
                return "???";

            IntPtr hToken = IntPtr.Zero;
            try
            {
                if (!OpenProcessToken(hProcess, TOKEN_QUERY, out hToken))
                    return "???";

                int dwLength;
                GetTokenInformation(hToken, TokenUser, IntPtr.Zero, 0, out dwLength);
                if (dwLength == 0)
                    return "???";

                IntPtr ptu = Marshal.AllocHGlobal(dwLength);
                try
                {
                    if (!GetTokenInformation(hToken, TokenUser, ptu, dwLength, out dwLength))
                        return "???";

                    IntPtr pSid = Marshal.ReadIntPtr(ptu);

                    StringBuilder name = new StringBuilder(128);
                    int cchName = name.Capacity;
                    StringBuilder domain = new StringBuilder(128);
                    int cchDomain = domain.Capacity;
                    SID_NAME_USE sidType;

                    if (!LookupAccountSidW(null, pSid, name, ref cchName, domain, ref cchDomain, out sidType))
                        return "???";

                    return domain.ToString() + "\\" + name.ToString();
                }
                finally
                {
                    Marshal.FreeHGlobal(ptu);
                }
            }
            catch (Exception ex)
            {
                Logger.Warning($"Failed to get process user: {ex.Message}");
                return "???";
            }
            finally
            {
                if (hToken != IntPtr.Zero)
                    CloseHandle(hToken);
            }
        }

        private static bool IsProcess64Bit(IntPtr hProcess)
        {
            try
            {
                bool isWow64;
                if (!IsWow64Process(hProcess, out isWow64))
                    return false;

                SYSTEM_INFO sysInfo;
                GetNativeSystemInfo(out sysInfo);

                return sysInfo.wProcessorArchitecture == PROCESSOR_ARCHITECTURE_AMD64 && !isWow64;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Failed to check process bitness: {ex.Message}");
                return false;
            }
        }

        private static string GetProcessIntegrityLevel(IntPtr hProcess)
        {
            if (hProcess == IntPtr.Zero)
                return "???";

            IntPtr hToken = IntPtr.Zero;
            try
            {
                if (!OpenProcessToken(hProcess, TOKEN_QUERY, out hToken))
                    return "???";

                int dwSize;
                GetTokenInformation(hToken, TokenIntegrityLevel, IntPtr.Zero, 0, out dwSize);
                if (dwSize == 0)
                    return "???";

                IntPtr pTIL = Marshal.AllocHGlobal(dwSize);
                try
                {
                    int dwLength;
                    if (!GetTokenInformation(hToken, TokenIntegrityLevel, pTIL, dwSize, out dwLength))
                        return "???";

                    IntPtr pSid = Marshal.ReadIntPtr(pTIL);

                    IntPtr pCount = GetSidSubAuthorityCount(pSid);
                    byte subAuthorityCount = Marshal.ReadByte(pCount);
                    IntPtr pRid = GetSidSubAuthority(pSid, (uint)(subAuthorityCount - 1));
                    int rid = Marshal.ReadInt32(pRid);

                    if (rid == SECURITY_MANDATORY_LOW_RID)
                        return "Low";
                    else if (rid >= SECURITY_MANDATORY_MEDIUM_RID && rid < SECURITY_MANDATORY_HIGH_RID)
                        return "Medium";
                    else if (rid >= SECURITY_MANDATORY_HIGH_RID && rid < SECURITY_MANDATORY_SYSTEM_RID)
                        return "High";
                    else if (rid >= SECURITY_MANDATORY_SYSTEM_RID)
                        return "System";
                    else
                        return "Unknown";
                }
                finally
                {
                    Marshal.FreeHGlobal(pTIL);
                }
            }
            catch (Exception ex)
            {
                Logger.Warning($"Failed to get process integrity level: {ex.Message}");
                return "???";
            }
            finally
            {
                if (hToken != IntPtr.Zero)
                    CloseHandle(hToken);
            }
        }

        private static uint GetProcessParentPID(IntPtr hProcess)
        {
            if (hProcess == IntPtr.Zero)
                return 0;

            try
            {
                PROCESS_BASIC_INFORMATION pbi = new PROCESS_BASIC_INFORMATION();
                int returnLength;
                int status = NtQueryInformationProcess(hProcess, 0, ref pbi, Marshal.SizeOf(pbi), out returnLength);
                if (status == 0)
                    return (uint)pbi.InheritedFromUniqueProcessId.ToInt64();
                return 0;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Failed to get parent PID: {ex.Message}");
                return 0;
            }
        }

        private static uint GetProcessCreationTime(IntPtr hProcess)
        {
            if (hProcess == IntPtr.Zero)
                return 0;

            try
            {
                long creationTime, exitTime, kernelTime, userTime;
                if (GetProcessTimes(hProcess, out creationTime, out exitTime, out kernelTime, out userTime))
                {
                    return (uint)((creationTime - FILETIME_TO_UNIX_EPOCH_DIFFERENCE) / FILETIME_TICKS_PER_SECOND);
                }
                return 0;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Failed to get process creation time: {ex.Message}");
                return 0;
            }
        }

        private static uint GetSessionId(Process proc)
        {
            try
            {
                return (uint)proc.SessionId;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Failed to get session ID: {ex.Message}");
                return unchecked((uint)-1);
            }
        }
    }
}
