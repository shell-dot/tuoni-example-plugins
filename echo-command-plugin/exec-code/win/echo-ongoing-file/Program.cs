using ExecUnitUtils;
using System;
using System.IO;
using System.Text;
using System.Threading;

namespace CommandEchoFile
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
            // Callback state outlives the pipe reader, which Run joins before return.
            using (ManualResetEvent stopped = new ManualResetEvent(false))
            {
                CommandRuntime.Run(pipeName, null, () => stopped.Set(), (client, configuration) =>
                {
                    if (configuration.Length < 4)
                        throw new InvalidDataException("The file configuration is truncated.");
                    int lines = BitConverter.ToInt32(configuration, 0);
                    if (lines <= 0)
                        throw new InvalidDataException("The line count must be positive.");
                    string[] messages = Encoding.UTF8.GetString(configuration, 4,
                        configuration.Length - 4).Split('\n');
                    client.sendConf_ongoingResult();
                    client.sendConf_stopWait(10 * 1000);
                    int index = 0;
                    while (index < messages.Length)
                    {
                        client.sendResult(Encoding.UTF8.GetBytes(messages[index++] + "\n"));
                        if (index % lines == 0) stopped.WaitOne(1000);
                        if (stopped.WaitOne(0))
                        {
                            client.sendResult(Encoding.UTF8.GetBytes("=== USER FORCED STOP ===\n"));
                            break;
                        }
                    }
                    client.sendResult(Encoding.UTF8.GetBytes("Stopping now\n"));
                });
            }
        }
    }
}