using ExecUnitUtils;
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Threading;

namespace CommandEchoOngoingMoreData
{
    public class Program
    {
        public static void start(string[] args) { Main(args); }

        static void Main(string[] args)
        {
#if TUONI_SHELLCODE
            string pipeName = "QQQWWWEEE";
#else
            if (args == null || args.Length != 1 || string.IsNullOrWhiteSpace(args[0]))
                return;
            string pipeName = args[0];
#endif
            // The reader only records bounded FIFO work. Output and completion
            // run on this invocation thread, so they cannot race each other.
            object gate = new object();
            Queue<byte[]> updates = new Queue<byte[]>();
            int bufferedBytes = 0;
            bool stopQueued = false;
            using (AutoResetEvent workReady = new AutoResetEvent(false))
            {
                Action<byte[]> enqueue = data =>
                {
                    lock (gate)
                    {
                        if (stopQueued) return;
                        bool stop = data == null || data.Length == 0 ||
                            (data.Length == 1 && data[0] == 0);
                        if (stop)
                        {
                            updates.Enqueue(null);
                            stopQueued = true;
                        }
                        else
                        {
                            if (updates.Count >= 4096 || data.Length > 64 * 1024 * 1024 - bufferedBytes)
                                throw new IOException("The queued update limit was exceeded.");
                            updates.Enqueue(data);
                            bufferedBytes += data.Length;
                        }
                    }
                    workReady.Set();
                };

                CommandRuntime.Run(pipeName, enqueue, () => enqueue(null), (client, configuration) =>
                {
                    client.sendConf_ongoingResult();
                    client.sendConf_stopWait(10 * 1000);
                    client.sendResult(Encoding.UTF8.GetBytes(
                        "Initial data: " + Encoding.UTF8.GetString(configuration) + "\n"));
                    while (true)
                    {
                        byte[] update = null;
                        bool hasUpdate;
                        lock (gate)
                        {
                            hasUpdate = updates.Count != 0;
                            if (hasUpdate)
                            {
                                update = updates.Dequeue();
                                if (update != null) bufferedBytes -= update.Length;
                            }
                        }
                        if (hasUpdate)
                        {
                            if (update == null) break;
                            client.sendResult(Encoding.UTF8.GetBytes(
                                "New data: " + Encoding.UTF8.GetString(update) + "\n"));
                        }
                        else
                        {
                            if (!client.IsConnected)
                                throw new IOException("The command pipe disconnected.");
                            workReady.WaitOne(100);
                        }
                    }
                });
                // Run closes/unblocks and joins the reader before this event or
                // callback state is released, including startup/reporting errors.
                updates.Clear();
            }
        }
    }
}