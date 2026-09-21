using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace DotNetAgent
{
    internal class ProcessRunner
    {
        private const uint STARTF_USESTDHANDLES = 0x00000100;
        private const uint CREATE_NO_WINDOW = 0x08000000;
        private const uint HANDLE_FLAG_INHERIT = 0x00000001;
        private const uint INFINITE = 0xFFFFFFFF;
        private const int PIPE_READ_BUFFER_SIZE = 4096;

        [StructLayout(LayoutKind.Sequential)]
        private struct SECURITY_ATTRIBUTES
        {
            public int nLength;
            public IntPtr lpSecurityDescriptor;
            [MarshalAs(UnmanagedType.Bool)]
            public bool bInheritHandle;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct STARTUPINFO
        {
            public int cb;
            public string lpReserved;
            public string lpDesktop;
            public string lpTitle;
            public int dwX, dwY, dwXSize, dwYSize;
            public int dwXCountChars, dwYCountChars;
            public int dwFillAttribute;
            public uint dwFlags;
            public short wShowWindow;
            public short cbReserved2;
            public IntPtr lpReserved2;
            public IntPtr hStdInput;
            public IntPtr hStdOutput;
            public IntPtr hStdError;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct PROCESS_INFORMATION
        {
            public IntPtr hProcess;
            public IntPtr hThread;
            public uint dwProcessId;
            public uint dwThreadId;
        }

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern bool CreateProcessW(
            string lpApplicationName,
            string lpCommandLine,
            IntPtr lpProcessAttributes,
            IntPtr lpThreadAttributes,
            bool bInheritHandles,
            uint dwCreationFlags,
            IntPtr lpEnvironment,
            string lpCurrentDirectory,
            ref STARTUPINFO lpStartupInfo,
            out PROCESS_INFORMATION lpProcessInformation);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CreatePipe(
            out IntPtr hReadPipe,
            out IntPtr hWritePipe,
            ref SECURITY_ATTRIBUTES lpPipeAttributes,
            uint nSize);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetHandleInformation(
            IntPtr hObject,
            uint dwMask,
            uint dwFlags);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool ReadFile(
            IntPtr hFile,
            byte[] lpBuffer,
            uint nNumberOfBytesToRead,
            out uint lpNumberOfBytesRead,
            IntPtr lpOverlapped);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint WaitForSingleObject(
            IntPtr hHandle,
            uint dwMilliseconds);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseHandle(IntPtr hObject);

        public static bool Run(string cmdline, bool getOutput, Action<byte[]> onStdoutChunk, out byte[] stderr, Action<IntPtr> onProcessCreated = null)
        {
            stderr = null;

            IntPtr hProcess = IntPtr.Zero;
            IntPtr hThread = IntPtr.Zero;
            IntPtr hStdOutRead = IntPtr.Zero, hStdOutWrite = IntPtr.Zero;
            IntPtr hStdErrRead = IntPtr.Zero, hStdErrWrite = IntPtr.Zero;

            try
            {
                STARTUPINFO si = new STARTUPINFO();
                si.cb = Marshal.SizeOf(typeof(STARTUPINFO));

                if (getOutput)
                {
                    SECURITY_ATTRIBUTES sa = new SECURITY_ATTRIBUTES();
                    sa.nLength = Marshal.SizeOf(typeof(SECURITY_ATTRIBUTES));
                    sa.bInheritHandle = true;
                    sa.lpSecurityDescriptor = IntPtr.Zero;

                    if (!CreatePipe(out hStdOutRead, out hStdOutWrite, ref sa, 0))
                    {
                        stderr = Encoding.UTF8.GetBytes("Failed to create stdout pipe");
                        return false;
                    }
                    if (!CreatePipe(out hStdErrRead, out hStdErrWrite, ref sa, 0))
                    {
                        stderr = Encoding.UTF8.GetBytes("Failed to create stderr pipe");
                        return false;
                    }

                    SetHandleInformation(hStdOutRead, HANDLE_FLAG_INHERIT, 0);
                    SetHandleInformation(hStdErrRead, HANDLE_FLAG_INHERIT, 0);

                    si.dwFlags = STARTF_USESTDHANDLES;
                    si.hStdOutput = hStdOutWrite;
                    si.hStdError = hStdErrWrite;
                    si.hStdInput = IntPtr.Zero;
                }

                PROCESS_INFORMATION pi;
                bool success = CreateProcessW(
                    null,
                    cmdline,
                    IntPtr.Zero,
                    IntPtr.Zero,
                    getOutput,
                    CREATE_NO_WINDOW,
                    IntPtr.Zero,
                    null,
                    ref si,
                    out pi);

                if (!success)
                {
                    int err = Marshal.GetLastWin32Error();
                    stderr = Encoding.UTF8.GetBytes("CreateProcess failed with error " + err);
                    return false;
                }

                hProcess = pi.hProcess;
                hThread = pi.hThread;
                onProcessCreated?.Invoke(hProcess);

                if (getOutput)
                {
                    CloseHandle(hStdOutWrite);
                    hStdOutWrite = IntPtr.Zero;
                    CloseHandle(hStdErrWrite);
                    hStdErrWrite = IntPtr.Zero;

                    using (MemoryStream stderrStream = new MemoryStream())
                    {
                        IntPtr hErrRead = hStdErrRead;
                        Thread stderrThread = new Thread(() => ReadPipeToStream(hErrRead, stderrStream));
                        stderrThread.IsBackground = true;
                        stderrThread.Start();

                        byte[] buffer = new byte[PIPE_READ_BUFFER_SIZE];
                        uint bytesRead;
                        while (ReadFile(hStdOutRead, buffer, (uint)buffer.Length, out bytesRead, IntPtr.Zero) && bytesRead > 0)
                        {
                            byte[] chunk = new byte[bytesRead];
                            Buffer.BlockCopy(buffer, 0, chunk, 0, (int)bytesRead);
                            onStdoutChunk(chunk);
                        }

                        stderrThread.Join();

                        WaitForSingleObject(hProcess, INFINITE);

                        byte[] stderrData = stderrStream.ToArray();
                        stderr = stderrData.Length > 0 ? stderrData : null;
                    }
                }
                else
                {
                    WaitForSingleObject(hProcess, INFINITE);
                }

                return true;
            }
            catch (Exception ex)
            {
                stderr = Encoding.UTF8.GetBytes(ex.ToString());
                return false;
            }
            finally
            {
                if (hStdOutRead != IntPtr.Zero) CloseHandle(hStdOutRead);
                if (hStdOutWrite != IntPtr.Zero) CloseHandle(hStdOutWrite);
                if (hStdErrRead != IntPtr.Zero) CloseHandle(hStdErrRead);
                if (hStdErrWrite != IntPtr.Zero) CloseHandle(hStdErrWrite);
                if (hThread != IntPtr.Zero) CloseHandle(hThread);
                if (hProcess != IntPtr.Zero) CloseHandle(hProcess);
            }
        }

        private static void ReadPipeToStream(IntPtr hPipe, MemoryStream stream)
        {
            byte[] buffer = new byte[PIPE_READ_BUFFER_SIZE];
            uint bytesRead;
            while (ReadFile(hPipe, buffer, (uint)buffer.Length, out bytesRead, IntPtr.Zero) && bytesRead > 0)
            {
                stream.Write(buffer, 0, (int)bytesRead);
            }
        }
    }
}
