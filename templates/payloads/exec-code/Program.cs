using System;

namespace PayloadTemplate
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            // TODO: Define configuration, lifecycle, and cleanup for your payload.
            // This is the generated payload program's process entry point. Read build-time
            // configuration and embedded listener material in the format written by the Java
            // payload serializer, and define whether args provide supported runtime overrides.
            // Validate required data before starting the payload's work, initialize the runtime
            // and supported listener components, and keep the process alive for their intended
            // lifetime. Arrange cancellation and shutdown so sockets, handles, threads, and other
            // owned resources are released even after startup or execution failures. Return zero
            // after successful completion and a nonzero exit code for a failed startup or run;
            // provide useful diagnostics without exposing secret configuration values.
            Console.Error.WriteLine("Payload template is not implemented.");
            return 1;
        }
    }
}

