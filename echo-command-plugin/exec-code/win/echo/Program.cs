using ExecUnitUtils;
using System;
using System.Text;

namespace CommandEcho
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
                if (message.StartsWith("ERR:"))
                    throw new Exception("Simulated exception: " + message.Substring(4));
                client.sendResult(configuration);
            });
        }
    }
}