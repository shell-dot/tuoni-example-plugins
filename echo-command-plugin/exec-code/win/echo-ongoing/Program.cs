using ExecUnitUtils;
using System;
using System.Text;
using System.Threading;

namespace CommandEchoOngoing
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
            CommandRuntime.Run(pipeName, null, null, (client, configuration) =>
            {
                string message = Encoding.UTF8.GetString(configuration);
                client.sendConf_ongoingResult();
                for (int counter = 0; counter < 4; ++counter)
                {
                    client.sendResult(Encoding.UTF8.GetBytes($"{counter}: {message}\n"));
                    Thread.Sleep(1000);
                }
                client.sendResult(Encoding.UTF8.GetBytes("Stopping now\n"));
            });
        }
    }
}