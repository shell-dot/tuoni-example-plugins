using System;

namespace ExecUnitUtils
{
    // Minimal command helper API skeleton; no messages are sent.
    internal class CommunicationNamedPipesCommand : CommunicationNamedPipes
    {
        public CommunicationNamedPipesCommand(string pipeName, Action<byte[]> newData, Action stop)
            : base(pipeName)
        {
            // Callback arguments describe extension points only.
        }

        public void sendResult(byte[] data)
        {
            throw new NotImplementedException("Result reporting is not implemented.");
        }

        public void sendError(byte[] message)
        {
            throw new NotImplementedException("Error reporting is not implemented.");
        }

        public void sendReturnSuccess()
        {
            throw new NotImplementedException("Completion reporting is not implemented.");
        }

        public void sendReturnFailed()
        {
            throw new NotImplementedException("Failure reporting is not implemented.");
        }
    }
}
