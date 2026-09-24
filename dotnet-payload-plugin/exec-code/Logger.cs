using System;

namespace DotNetAgent
{
    internal static class Logger
    {
        internal static void Info(string message)
        {
            Console.WriteLine("[INFO] " + message);
        }

        internal static void Warning(string message)
        {
            Console.WriteLine("[WARNING] " + message);
        }
    }
}
