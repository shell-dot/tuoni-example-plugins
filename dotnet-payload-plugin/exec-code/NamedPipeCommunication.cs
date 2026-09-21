using System;
using System.IO;
using System.IO.Pipes;
using System.Threading;

namespace DotNetAgent
{
    internal class NamedPipeCommunication
    {
        private NamedPipeServerStream _pipeServer;

        private readonly object _lock = new object();
        private readonly ManualResetEventSlim _listeningEvent = new ManualResetEventSlim(false);

        private const byte TLV_INITIAL_DATA = 0x1;

        public bool CreatePipe(string pipeName)
        {
            try
            {
                lock (_lock)
                {
                    _pipeServer = new NamedPipeServerStream(pipeName, PipeDirection.InOut, 1, PipeTransmissionMode.Byte, PipeOptions.Asynchronous);
                }
                return true;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Failed to create pipe: {ex.Message}");
                return false;
            }
        }

        public bool WaitConnection(byte[] initialData, Action<byte[]> callbackData, Action callbackClosed, int timeout = 4000)
        {
            try
            {
                NamedPipeServerStream pipe;
                lock (_lock)
                {
                    pipe = _pipeServer;
                }

                if (pipe == null)
                    return false;

                IAsyncResult connectResult = pipe.BeginWaitForConnection(null, null);
                _listeningEvent.Set();
                if (!connectResult.AsyncWaitHandle.WaitOne(timeout))
                    return false;

                pipe.EndWaitForConnection(connectResult);

                byte[] initialBytes = initialData ?? new byte[0];
                TLV tlvWrapper = new TLV(TLV_INITIAL_DATA, initialBytes);
                initialBytes = tlvWrapper.GetFullBuffer();
                byte[] lengthPrefix = BitConverter.GetBytes((int)initialBytes.Length);
                pipe.Write(lengthPrefix, 0, 4);
                if (initialBytes.Length > 0)
                    pipe.Write(initialBytes, 0, initialBytes.Length);
                pipe.Flush();

                Thread readThread = new Thread(() => ReadLoop(pipe, callbackData, callbackClosed));
                readThread.IsBackground = true;
                readThread.Start();

                return true;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Pipe connection failed: {ex.Message}");
                return false;
            }
        }

        private void ReadLoop(NamedPipeServerStream pipe, Action<byte[]> callbackData, Action callbackClosed)
        {
            try
            {
                byte[] lengthBuffer = new byte[4];
                while (pipe.IsConnected)
                {
                    if (!ReadExact(pipe, lengthBuffer, 4))
                        break;

                    int dataLength = BitConverter.ToInt32(lengthBuffer, 0);
                    if (dataLength < 0)
                        break;

                    byte[] data = new byte[dataLength];
                    if (dataLength > 0 && !ReadExact(pipe, data, dataLength))
                        break;

                    callbackData?.Invoke(data);
                }
            }
            catch (Exception ex) { Logger.Warning($"Pipe read loop error: {ex.Message}"); }

            callbackClosed?.Invoke();
        }

        private bool ReadExact(Stream stream, byte[] buffer, int count)
        {
            int offset = 0;
            while (offset < count)
            {
                int read = stream.Read(buffer, offset, count - offset);
                if (read == 0)
                    return false;
                offset += read;
            }
            return true;
        }

        public void WaitUntilListening()
        {
            _listeningEvent.Wait();
        }

        public bool Send(byte[] data)
        {
            try
            {
                lock (_lock)
                {
                    if (_pipeServer == null || !_pipeServer.IsConnected)
                        return false;

                    byte[] lengthPrefix = BitConverter.GetBytes((int)data.Length);
                    _pipeServer.Write(lengthPrefix, 0, 4);
                    if (data.Length > 0)
                        _pipeServer.Write(data, 0, data.Length);
                    _pipeServer.Flush();
                }
                return true;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Pipe send failed: {ex.Message}");
                return false;
            }
        }

        public bool Close()
        {
            try
            {
                lock (_lock)
                {
                    if (_pipeServer != null)
                    {
                        if (_pipeServer.IsConnected)
                            _pipeServer.Disconnect();
                        _pipeServer.Dispose();
                        _pipeServer = null;
                    }
                }
                return true;
            }
            catch (Exception ex)
            {
                Logger.Warning($"Pipe close failed: {ex.Message}");
                return false;
            }
        }
    }
}
