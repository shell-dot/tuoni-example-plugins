using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;

namespace ExecUnitUtils
{
    internal class CommunicationNamedPipesListener : CommunicationNamedPipes
    {
        protected const byte MessageTypeCallback = 0x20;
        protected const byte MessageTypeResponse1 = 0x21;
        protected const byte MessageTypeResponse2 = 0x22;
        protected const byte MessageTypeNewData = 0x23;
        protected const byte ChildTypeCommand = 0x1;
        protected const byte ChildTypeSeqNr = 0x2;
        protected const byte ChildTypeData = 0x4;
        protected int _seqNr;
        Action<byte[]> _callback;
        protected readonly Dictionary<int, TLV> _responses;
        protected readonly Dictionary<int, EventWaitHandle> _signals;
        protected readonly object _responseLock;

        public CommunicationNamedPipesListener(string pipeName, Action<byte[]> callback) : base(pipeName)
        {
            _responses = new Dictionary<int, TLV>();
            _signals = new Dictionary<int, EventWaitHandle>();
            _responseLock = new object();
            _seqNr = 1;
            _callback = callback;
            Disconnected += WakeResponseWaiters;
        }

        public void SetCallback(Action<byte[]> callback) { _callback = callback; }
        public byte[] GetMetadata() { return RequestData(MessageTypeResponse1); }
        public byte[] GetDataToSend() { return RequestData(MessageTypeResponse2); }

        private byte[] RequestData(byte type)
        {
            if (!_active) return null;
            int seq = GetNextSeqNr();
            EventWaitHandle signal = new EventWaitHandle(false, EventResetMode.AutoReset);
            bool registered = false;
            try
            {
                lock (_responseLock)
                {
                    if (!_active) return null;
                    // Register before sending: a fast response must have a bounded owner.
                    _signals.Add(seq, signal);
                    registered = true;
                }
                TLV tlv = new TLV(type);
                tlv.AddChild(new TLV(ChildTypeCommand, new byte[] { 0x1 }));
                tlv.AddChild(new TLV(ChildTypeSeqNr, BitConverter.GetBytes(seq)));
                if (!PutData(tlv.GetFullBuffer())) return null;
                byte[] data = WaitForResponseData(seq, Timeout.Infinite);
                return data;
            }
            finally
            {
                lock (_responseLock)
                {
                    if (registered)
                    {
                        _signals.Remove(seq);
                        _responses.Remove(seq);
                    }
                    signal.Dispose();
                }
            }
        }

        public bool NewDataFromC2(byte[] data)
        {
            if (!_active) return false;
            try { return PutData(new TLV(MessageTypeNewData, data).GetFullBuffer()); }
            catch (Exception) { return false; }
        }

        protected override bool HandleIncomingData(TLV tlv)
        {
            if (tlv.Type == MessageTypeCallback)
            {
                Action<byte[]> callback = _callback;
                TLV child = tlv.GetChild(ChildTypeData);
                byte[] data = child != null ? child.GetAsBytes() : null;
                if (callback != null && data != null) callback(data);
                return true;
            }

            if (tlv.Type == MessageTypeResponse1 || tlv.Type == MessageTypeResponse2)
            {
                TLV seqChild = tlv.GetChild(ChildTypeSeqNr);
                if (seqChild == null || seqChild.IsParent ||
                    seqChild.Data == null || seqChild.Data.Length != 4)
                    throw new IOException("Invalid response sequence.");
                int id = seqChild.GetAsInt32();
                lock (_responseLock)
                {
                    EventWaitHandle signal;
                    // Unsolicited/late responses cannot accumulate in the dictionary.
                    if (_signals.TryGetValue(id, out signal))
                    {
                        _responses[id] = tlv;
                        signal.Set();
                    }
                }
                return true;
            }
            return false;
        }

        protected byte[] WaitForResponseData(int id, int timeoutMs)
        {
            EventWaitHandle signal;
            lock (_responseLock)
            {
                if (!_active || !_signals.TryGetValue(id, out signal)) return null;
            }
            if (!signal.WaitOne(timeoutMs)) return null;
            lock (_responseLock)
            {
                if (!_active) return null;
                TLV response;
                if (!_responses.TryGetValue(id, out response)) return null;
                TLV child = response.GetChild(ChildTypeData);
                return child != null ? child.GetAsBytes() : null;
            }
        }

        private void WakeResponseWaiters()
        {
            lock (_responseLock)
                foreach (EventWaitHandle signal in _signals.Values)
                    signal.Set();
        }

        protected int GetNextSeqNr()
        {
            lock (_sendLock) { return _seqNr++; }
        }

        public override void Dispose()
        {
            base.Dispose();
            // Each request owns its wait handle and releases it in finally after
            // disconnect wakes it. Never dispose a handle under an active WaitOne.
            lock (_responseLock)
            {
                _callback = null;
                _responses.Clear();
            }
        }
    }
}
