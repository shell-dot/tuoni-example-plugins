using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace DotNetAgent
{
    internal class TLV
    {
        public byte Type { get; private set; } = 0;
        public bool IsParent { get; private set; } = false;
        private Dictionary<byte, List<TLV>> _children = null;
        public byte[] Data { get; private set; } = null;
        public uint FullSize { get; private set; } = 0;

        public TLV()
        {
        }

        public TLV(byte typeIn, byte[] dataIn)
        {
            Type = typeIn;
            Data = dataIn ?? throw new ArgumentNullException(nameof(dataIn));
            IsParent = false;
            FullSize = checked((uint)dataIn.Length + 5);
        }

        public TLV(byte typeIn)
        {
            Type = typeIn;
            IsParent = true;
            _children = new Dictionary<byte, List<TLV>>();
            FullSize = 5;
        }

        public bool Load(byte[] buffer, int offset = 0)
        {
            if (buffer.Length - offset < 5)
                return false;

            Type = (byte)(buffer[offset] & 0x7F);
            IsParent = (buffer[offset] & 0x80) > 0;
            offset += 1;

            uint len = BitConverter.ToUInt32(buffer, offset);
            offset += 4;

            if (buffer.Length - offset < len)
                return false;

            FullSize = len + 5;

            if (!IsParent)
            {
                Data = new byte[len];
                Array.Copy(buffer, offset, Data, 0, (int)len);
                return true;
            }

            _children = new Dictionary<byte, List<TLV>>();
            uint remaining = len;
            while (remaining != 0)
            {
                TLV child = new TLV();
                if (!child.Load(buffer, offset))
                    return false;

                AddChildInternal(child);
                if (child.FullSize > remaining)
                    return false;

                offset += (int)child.FullSize;
                remaining -= child.FullSize;
            }
            return true;
        }

        public bool AddChild(TLV child)
        {
            if (!IsParent)
                throw new InvalidOperationException("Cannot add child to a non-parent TLV.");

            AddChildInternal(child);
            FullSize = checked(FullSize + child.FullSize);
            return true;
        }

        private void AddChildInternal(TLV child)
        {
            if (!_children.ContainsKey(child.Type))
                _children.Add(child.Type, new List<TLV>());
            _children[child.Type].Add(child);
        }

        public TLV GetChild(byte childType, int idx = 0)
        {
            if (_children == null || !_children.ContainsKey(childType))
                return null;
            if (idx < 0 || idx >= _children[childType].Count)
                return null;
            return _children[childType][idx];
        }

        public int GetChildCount(byte childType)
        {
            return _children?.ContainsKey(childType) ?? false ? _children[childType].Count : 0;
        }

        public bool HasChild(byte childType)
        {
            return _children?.ContainsKey(childType) ?? false;
        }

        public byte[] GetFullBuffer()
        {
            if (FullSize > int.MaxValue)
                throw new InvalidOperationException("TLV too large for MemoryStream (exceeds int.MaxValue).");

            using (var stream = new MemoryStream((int)FullSize))
            {
                using (var writer = new BinaryWriter(stream))
                {
                    WriteFullBuffer(writer);
                    return stream.ToArray();
                }
            }
        }

        private void WriteFullBuffer(BinaryWriter writer)
        {
            writer.Write((byte)(Type | (IsParent ? 0x80 : 0)));

            uint valueLen = FullSize - 5;
            writer.Write(valueLen);

            if (!IsParent)
            {
                writer.Write(Data);
            }
            else
            {
                foreach (var childList in _children.Values)
                    foreach (var child in childList)
                        child.WriteFullBuffer(writer);
            }
        }

        public string GetAsString()
        {
            if (IsParent || Data == null) return null;
            return Encoding.UTF8.GetString(Data);
        }

        private void ValidateDataLength(int expectedLength)
        {
            if (IsParent || Data == null || Data.Length != expectedLength)
                throw new InvalidOperationException("Invalid data content");
        }

        public byte GetAsByte()
        {
            ValidateDataLength(1);
            return Data[0];
        }

        public sbyte GetAsSByte()
        {
            ValidateDataLength(1);
            return (sbyte)Data[0];
        }

        public bool GetAsBool()
        {
            ValidateDataLength(1);
            return Data[0] != 0;
        }

        public short GetAsInt16()
        {
            ValidateDataLength(2);
            return BitConverter.ToInt16(Data, 0);
        }

        public ushort GetAsUInt16()
        {
            ValidateDataLength(2);
            return BitConverter.ToUInt16(Data, 0);
        }

        public int GetAsInt32()
        {
            ValidateDataLength(4);
            return BitConverter.ToInt32(Data, 0);
        }

        public uint GetAsUInt32()
        {
            ValidateDataLength(4);
            return BitConverter.ToUInt32(Data, 0);
        }

        public long GetAsInt64()
        {
            ValidateDataLength(8);
            return BitConverter.ToInt64(Data, 0);
        }

        public ulong GetAsUInt64()
        {
            ValidateDataLength(8);
            return BitConverter.ToUInt64(Data, 0);
        }

        public float GetAsSingle()
        {
            ValidateDataLength(4);
            return BitConverter.ToSingle(Data, 0);
        }

        public double GetAsDouble()
        {
            ValidateDataLength(8);
            return BitConverter.ToDouble(Data, 0);
        }

        public byte[] GetAsBytes()
        {
            if (IsParent || Data == null) return null;
            byte[] copy = new byte[Data.Length];
            Array.Copy(Data, copy, Data.Length);
            return copy;
        }

        public override string ToString()
        {
            return $"TLV(Type={Type}, IsParent={IsParent}, FullSize={FullSize}, ChildrenCount={(_children?.Count ?? 0)})";
        }
    }
}
