using System;

namespace ExecUnitUtils
{
    // Minimal data-container skeleton; encoding and decoding are unimplemented.
    public class TLV
    {
        public byte Type { get; private set; }
        public byte[] Data { get; private set; }

        public TLV() { }

        public TLV(byte typeIn, byte[] dataIn)
        {
            Type = typeIn;
            Data = dataIn;
        }

        public bool Load(byte[] buffer, int offset = 0)
        {
            // TODO: Validate input lengths before decoding.
            throw new NotImplementedException("TLV decoding is not implemented.");
        }

        public byte[] GetFullBuffer()
        {
            // TODO: Define serialization for this data container.
            throw new NotImplementedException("TLV encoding is not implemented.");
        }
    }
}
