using System;
using System.IO;
using System.Text;

namespace ExecUnitUtils
{
    // One invocation owns startup, checked completion and reader cleanup.
    internal static class CommandRuntime
    {
        public static void Run(string pipeName, Action<byte[]> newData, Action stop,
            Action<CommunicationNamedPipesCommand, byte[]> execute)
        {
            CommunicationNamedPipesCommand client = null;
            bool succeeded = false;
            try
            {
                client = new CommunicationNamedPipesCommand(pipeName, newData, stop);
                byte[] configuration = client.Connect();
                if (configuration == null)
                    throw new IOException("The command pipe did not provide a valid startup frame.");
                execute(client, configuration);
                succeeded = true;
            }
            catch (Exception error)
            {
                // A diagnostic failure must not skip the completion/cleanup owner.
                try
                {
                    if (client != null && client.IsConnected)
                        client.sendError(Encoding.UTF8.GetBytes(error.Message));
                }
                catch (Exception) { }
            }
            finally
            {
                try
                {
                    if (client != null && client.IsConnected)
                    {
                        if (succeeded) client.sendReturnSuccess();
                        else client.sendReturnFailed();
                    }
                }
                catch (Exception) { }
                finally
                {
                    if (client != null) client.Dispose();
                }
            }
        }
    }
}
