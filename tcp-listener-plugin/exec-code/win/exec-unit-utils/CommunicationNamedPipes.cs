using System;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Threading;
using Microsoft.Win32.SafeHandles;

namespace ExecUnitUtils
{
    // Reference API, with local host-safety and deterministic cleanup hardening.
    public class CommunicationNamedPipes : IDisposable
    {
        protected const int DefaultConnectTimeoutMs = 5000;
        protected const int DefaultStartupTimeoutMs = 10000;
        protected const int MaxFrameSize = 64 * 1024 * 1024;
        protected volatile bool _active;
        protected NamedPipeClientStream _client;
        protected BinaryReader _reader;
        protected BinaryWriter _writer;
        protected Thread _listenThread;
        protected readonly object _sendLock;
        protected CancellationTokenSource _cts;
        int _disposed;
        int _disconnected;

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool CancelIoEx(SafePipeHandle pipe, IntPtr operation);

        public event Action Disconnected;
        public bool IsConnected { get { return _active && Volatile.Read(ref _disposed) == 0; } }
        protected virtual bool HasCallbacks { get { return true; } }

        public CommunicationNamedPipes(string name)
        {
            _sendLock = new object();
            _cts = new CancellationTokenSource();
            try
            {
                _client = new NamedPipeClientStream(".", name, PipeDirection.InOut, PipeOptions.Asynchronous);
            }
            catch
            {
                _cts.Dispose();
                throw;
            }
        }

        public byte[] Connect(int timeoutMs = 10000)
        {
            Timer startupTimer = null;
            ManualResetEvent timerDrained = null;
            int startupTimedOut = 0;
            try
            {
                if (Volatile.Read(ref _disposed) != 0) return null;
                _client.Connect(timeoutMs);
                _reader = new BinaryReader(_client);
                _writer = new BinaryWriter(_client);
                _active = true;
                timerDrained = new ManualResetEvent(false);
                startupTimer = new Timer(ignored =>
                {
                    Interlocked.Exchange(ref startupTimedOut, 1);
                    // Only the owned pipe is touched here; user callbacks and
                    // connection-loss notification stay on the calling thread.
                    CancelAndClosePipe();
                }, null, timeoutMs > 0 ? timeoutMs : DefaultStartupTimeoutMs, Timeout.Infinite);
                byte[] data = GetData();
                // No timeout callback can survive startup or overlap the reader.
                DrainStartupTimer(ref startupTimer, timerDrained);
                TLV tlv = new TLV();
                // Startup is one leaf: a malformed envelope cannot be empty config.
                if (Volatile.Read(ref startupTimedOut) != 0 || data == null || (data[0] & 0x80) != 0 ||
                    !tlv.Load(data, 0) || tlv.FullSize != data.Length)
                {
                    MarkDisconnected();
                    return null;
                }
                if (HasCallbacks)
                {
                    _listenThread = new Thread(ListenForMessages) { IsBackground = true };
                    _listenThread.Start();
                }
                return tlv.Data;
            }
            catch (Exception)
            {
                MarkDisconnected();
                return null;
            }
            finally
            {
                DrainStartupTimer(ref startupTimer, timerDrained);
                if (timerDrained != null) timerDrained.Dispose();
                if (!_active) Dispose();
            }
        }

        public void Close() { Dispose(); }
        protected virtual bool HandleIncomingData(TLV tlv) { return false; }

        private static void DrainStartupTimer(ref Timer timer, ManualResetEvent drained)
        {
            if (timer == null) return;
            if (timer.Dispose(drained))
            {
                // Drain queued/running callbacks even if the owner is interrupted.
                while (true)
                {
                    try { drained.WaitOne(); break; }
                    catch (ThreadInterruptedException) { }
                }
            }
            timer = null;
        }

        private void CancelAndClosePipe()
        {
            try
            {
                if (_client != null) CancelIoEx(_client.SafePipeHandle, IntPtr.Zero);
            }
            catch (Exception) { } // Failed startup or non-Windows utility checks.
            try { if (_client != null) _client.Dispose(); } catch (Exception) { }
        }

        protected void MarkDisconnected()
        {
            _active = false;
            if (Interlocked.Exchange(ref _disconnected, 1) != 0) return;
            // Unblock any concurrent I/O before notifying its owner.
            CancelAndClosePipe();
            // Disconnect notification must never escape an owned reader thread.
            Action handler = Disconnected;
            if (handler != null)
                try { handler(); } catch (Exception) { }
        }

        protected void ListenForMessages()
        {
            try
            {
                while (_active && !_cts.IsCancellationRequested)
                {
                    byte[] data = GetData();
                    if (data == null) break;
                    TLV tlv = new TLV();
                    if (!tlv.Load(data, 0) || tlv.FullSize != data.Length)
                        throw new IOException("Invalid IPC TLV frame.");
                    HandleIncomingData(tlv);
                }
            }
            catch (Exception) { }
            finally { MarkDisconnected(); }
        }

        protected byte[] GetData()
        {
            if (!_active) return null;
            try
            {
                int length = _reader.ReadInt32();
                if (length < 5 || length > MaxFrameSize)
                    throw new IOException("Invalid IPC frame length.");
                byte[] data = _reader.ReadBytes(length);
                if (data.Length != length)
                    throw new EndOfStreamException("Truncated IPC frame.");
                return data;
            }
            catch (Exception)
            {
                MarkDisconnected();
                return null;
            }
        }

        protected bool PutData(byte[] data)
        {
            lock (_sendLock)
            {
                if (!_active) return false;
                try
                {
                    if (data == null || data.Length < 5 || data.Length > MaxFrameSize)
                        throw new IOException("Invalid IPC frame length.");
                    _writer.Write(data.Length);
                    _writer.Write(data);
                    _writer.Flush();
                    return true;
                }
                catch (Exception)
                {
                    MarkDisconnected();
                    return false;
                }
            }
        }

        public virtual void Dispose()
        {
            // _active describes transport state, not whether resources are owned.
            if (Interlocked.Exchange(ref _disposed, 1) != 0) return;
            MarkDisconnected();
            try { _cts.Cancel(); } catch (Exception) { }
            // Close before taking the write lock to unblock outstanding I/O.
            try { if (_client != null) _client.Dispose(); } catch (Exception) { }
            if (_listenThread != null && _listenThread != Thread.CurrentThread && _listenThread.IsAlive)
                _listenThread.Join();
            lock (_sendLock)
            {
                try { if (_reader != null) _reader.Dispose(); } catch (Exception) { }
                try { if (_writer != null) _writer.Dispose(); } catch (Exception) { }
            }
            _cts.Dispose();
            Disconnected = null;
        }
    }
}
