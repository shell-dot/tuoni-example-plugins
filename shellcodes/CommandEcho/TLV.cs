using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace CommandEcho
{
    internal class TLV
    {
        public byte type { get; private set; } = 0;
        public bool isParent { get; private set; } = false;
        public Dictionary<byte, List<TLV>> children = null;
        public byte[] data { get; private set; } = null;
        public UInt32 fullSize { get; private set; } = 0;

        public TLV()
        {
        }

        public TLV(byte typeIn, byte[] dataIn)
        {
            type = typeIn;
            data = dataIn;
            isParent = false;
            fullSize = (UInt32)data.Length + 5;
        }

        public TLV(byte typeIn)
        {
            type = typeIn;
            isParent = true;
            children = new Dictionary<byte, List<TLV>>();
            fullSize = 5;
        }

        public bool load(byte[] buffer, int offset = 0)
        {
            if (buffer.Length - offset < 5)
                return false;
            type = (byte)(buffer[offset] & 0x7F);
            isParent = (buffer[offset] & 0x80) > 0;
            offset += 1;
            UInt32 len;
            bool iLittle = BitConverter.IsLittleEndian;
            len = BitConverter.ToUInt32(buffer, offset);
            offset += 4;
            if (buffer.Length - offset < len)
                return false;
            fullSize = len + 5;

            if (!isParent)
            {
                data = new byte[len];
                Array.Copy(buffer, offset, data, 0, len);
                return true;
            }

            children = new Dictionary<byte, List<TLV>>();
            while (len != 0)
            {
                TLV child = new TLV();
                if (!child.load(buffer, offset))
                    return false;
                addChild(child);
                if (child.fullSize > len)
                    return false;
                offset += (int)child.fullSize;
                len -= child.fullSize;
            }
            return true;
        }

        public bool addChild(TLV child)
        {
            if (!children.ContainsKey(child.type))
                children.Add(child.type, new List<TLV>());
            children[child.type].Add(child);
            fullSize += child.fullSize;
            return true;
        }

        public TLV getChild(byte childType, int idx)
        {
            if (!children.ContainsKey(childType))
                return null;
            return children[childType][idx];
        }

        public TLV getChild(byte childType)
        {
            return getChild(childType, 0);
        }

        public int getChildCount(byte childType)
        {
            if (!children.ContainsKey(childType))
                return 0;
            return children[childType].Count;
        }

        public byte[] getFullBuffer()
        {
            MemoryStream stream = new MemoryStream((int)fullSize);
            using (BinaryWriter writer = new BinaryWriter(stream))
            {
                getFullBuffer(writer);
            }
            return stream.ToArray();
        }

        private bool getFullBuffer(BinaryWriter writer)
        {
            writer.Write((byte)(type | (isParent ? 0x80 : 0)));
            writer.Write((UInt32)(fullSize - 5));
            if (!isParent)
                writer.Write(data);
            else
                foreach (List<TLV> childArr in children.Values)
                    foreach (TLV child in childArr)
                        if (!child.getFullBuffer(writer))
                            return false;
            return true;
        }

        public String getDataAsString()
        {
            return System.Text.Encoding.UTF8.GetString(data);
        }

        public Int32 getDataAsInt32()
        {
            return BitConverter.ToInt32(data, 0);
        }

    }

}
