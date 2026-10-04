using System;
using System.IO;
using ExecUnitUtils;

namespace ListenerExecUnitTemplate
{
    internal static class Program
    {
        // Patched by the Java plugin when generating Windows shellcode.
        private const string PipeNamePlaceholder = "QQQWWWEEE";

        private static int Main(string[] args)
        {
            CommunicationNamedPipesListener pipe = null;
            try
            {
                pipe = new CommunicationNamedPipesListener(PipeNamePlaceholder, null);
                byte[] configuration = Initialize(pipe);
                WaitForStop(pipe, configuration);
                return 0;
            }
            catch (Exception)
            {
                // Contain startup/transport failures inside the agent host. There
                // is no command-style terminal report in the listener protocol.
                return 1;
            }
            finally
            {
                Cleanup(pipe);
            }
        }

        private static byte[] Initialize(CommunicationNamedPipesListener pipe)
        {
            byte[] configuration = pipe.Connect(10000);
            if (configuration == null)
                throw new IOException("Unable to receive listener configuration.");
            if (configuration.Length != 0)
                throw new ArgumentException("The template listener expects an empty configuration payload.");
            // TODO: Initialize the data traffic channel using the validated settings.
            return configuration;
        }

        private static void WaitForStop(CommunicationNamedPipesListener pipe, byte[] configuration)
        {
            // TODO: Forward agent metadata/requests to Java through the data traffic
            // channel and return queued commands through NewDataFromC2.
            // The idle default makes no traffic requests and stays alive until the
            // local agent closes its pipe. Wait for the owned reader to finish.
            pipe.WaitForDisconnect();
        }

        private static void Cleanup(CommunicationNamedPipesListener pipe)
        {
            // TODO: Stop/unblock and join data-channel workers before pipe disposal.
            // No invocation-owned work may survive return to the agent host.
            if (pipe != null)
            {
                try { pipe.Dispose(); }
                catch (Exception) { }
            }
        }
    }
}
