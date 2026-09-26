using System;

namespace ExecUnitUtils
{
    // API skeleton only. Constructing this object does not open a pipe.
    public class CommunicationNamedPipes : IDisposable
    {
        public string PipeName { get; private set; }

        public CommunicationNamedPipes(string name)
        {
            PipeName = name;
        }

        public byte[] Connect(int timeoutMs = 10000)
        {
            throw new NotImplementedException("Pipe connection and configuration exchange are not implemented.");
        }

        public void Close()
        {
            // TODO: Release owned resources, including after partial initialization.
            // Keep cleanup safe to call more than once.
        }

        public void Dispose()
        {
            Close();
        }
    }
}
