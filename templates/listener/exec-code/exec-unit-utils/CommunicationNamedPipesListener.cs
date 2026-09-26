using System;

namespace ExecUnitUtils
{
    // Minimal listener helper API skeleton; no callbacks or messages are dispatched.
    internal class CommunicationNamedPipesListener : CommunicationNamedPipes
    {
        public CommunicationNamedPipesListener(string pipeName, Action<byte[]> callback)
            : base(pipeName)
        {
            // The callback argument describes an extension point only.
        }

        public void SetCallback(Action<byte[]> callback)
        {
            throw new NotImplementedException("Callback registration is not implemented.");
        }

        public byte[] GetMetadata()
        {
            throw new NotImplementedException("Metadata exchange is not implemented.");
        }

        public byte[] GetDataToSend()
        {
            throw new NotImplementedException("Data retrieval is not implemented.");
        }

        public bool NewDataFromC2(byte[] data)
        {
            throw new NotImplementedException("Data forwarding is not implemented.");
        }
    }
}
