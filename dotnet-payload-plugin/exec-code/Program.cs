using System;
using System.Threading;

namespace DotNetAgent
{
    internal class Program
    {
        static void Main(string[] args)
        {
            try
            {
                Logger.Info("Starting to load in conf");
                byte[] startConf = GlobalConf.GetAddedSetupBuffer();
                Logger.Info($"Loaded in {startConf.Length} bytes as initial conf");
                MessagesManager.LoadData(startConf);
                Logger.Info("Initializing metadata");
                Metadata.Initialize();
                Logger.Info("Starting listeners");
                ListenerManager.StartSingleListener();
                Logger.Info("Everything is running");
                Thread.Sleep(Timeout.Infinite);
            }
            catch (Exception ex)
            {
                Logger.Warning($"Fatal startup error: {ex}");
            }
        }
    }
}
