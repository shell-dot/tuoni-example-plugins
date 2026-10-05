using System;
using System.IO;
using System.Text;
using ExecUnitUtils;

namespace CommandExecUnitTemplate
{
    public static class Program
    {
        // The Java plugin patches this UTF-16LE placeholder in the shellcode.
        private const string PipeNamePlaceholder = "QQQWWWEEE";

        // Reflection entry point for DOTNET_DLL; wait for all work before returning.
        public static void start(string[] args)
        {
            Main(args);
        }

        private static int Main(string[] args)
        {
#if TUONI_SHELLCODE
            string pipeName = PipeNamePlaceholder;
#else
            if (args == null || args.Length != 1 || string.IsNullOrWhiteSpace(args[0]))
                return 1;
            string pipeName = args[0];
#endif
            CommunicationNamedPipesCommand pipe = null;
            bool succeeded = false;
            int exitCode = 1;
            try
            {
                // Keep ownership local to this invocation, including failed startup.
                pipe = new CommunicationNamedPipesCommand(pipeName, null, null);
                byte[] configuration = Initialize(pipe);
                Execute(pipe, configuration);
                succeeded = true;
            }
            catch (Exception error)
            {
                // Diagnostic reporting is optional; it must not bypass completion.
                if (pipe != null)
                {
                    try { pipe.sendError(Encoding.UTF8.GetBytes(error.Message)); }
                    catch (Exception) { }
                }
            }
            finally
            {
                if (pipe != null)
                {
                    try
                    {
                        bool reported = Complete(pipe, succeeded);
                        exitCode = succeeded && reported ? 0 : 1;
                    }
                    catch (Exception) { exitCode = 1; }
                    finally { Cleanup(pipe); }
                }
            }
            return exitCode;
        }

        private static byte[] Initialize(CommunicationNamedPipesCommand pipe)
        {
            byte[] configuration = pipe.Connect(10000);
            if (configuration == null)
                throw new IOException("Unable to receive command configuration.");
            if (configuration.Length != 0)
                throw new ArgumentException("The template command expects an empty configuration payload.");
            return configuration;
        }

        private static void Execute(CommunicationNamedPipesCommand pipe, byte[] configuration)
        {
            // Add command behavior here. Send complete UTF-8 text payloads and
            // check delivery before Complete selects the terminal outcome.
            if (!pipe.sendResult(Encoding.UTF8.GetBytes("DONE")))
                throw new IOException("Unable to send command result.");
        }

        private static bool Complete(CommunicationNamedPipesCommand pipe, bool succeeded)
        {
            // Exactly one terminal attempt; never replay a failed/partial frame.
            return succeeded ? pipe.sendReturnSuccess() : pipe.sendReturnFailed();
        }

        private static void Cleanup(CommunicationNamedPipesCommand pipe)
        {
            // Stop and join any operation workers added to Execute before completion.
            // No invocation-owned work may survive return to the agent host.
            try { pipe.Dispose(); }
            catch (Exception) { }
        }
    }
}
