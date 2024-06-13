using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Pipes;
using System.Linq;
using System.Runtime.Remoting.Messaging;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Xml.Linq;

namespace CommandEcho
{
    internal class Program
    {
        static void Main(string[] args)
        {
            //Creating connection to the named pipe listener in agent (QQQWWWEEE is likely overwritten in reality)
            NamedPipeClientStream client = new NamedPipeClientStream(".", "QQQWWWEEE", PipeDirection.InOut, PipeOptions.Asynchronous);
            client.Connect();

            //Supporting objects for reading and writing to the pipe
            BinaryReader reader = new BinaryReader(client);
            BinaryWriter writer = new BinaryWriter(client);

            //Lets read the data from the pipe (4 byte size of the data, then the data)
            int len = reader.ReadInt32();
            byte[] data = reader.ReadBytes(len);

            try
            {
                //Parse the input that should be TLV structure with type 0x5 (configuration data type)
                TLV tlv = new TLV();
                if (!tlv.load(data))
                {
                    throw new Exception("Failed to load TLV data");
                }
                if(tlv.type != 5)
                {
                    throw new Exception("TLV type is not 5 but " + (int)tlv.type);
                }
                byte[] messageBytes = tlv.data;

                //Return same bytes back as data (0x30 is TLV type for result data)
                tlv = new TLV(0x30, messageBytes);
                data = tlv.getFullBuffer();
                writer.Write(data.Length);
                writer.Write(data);
                writer.Flush();

                //Return the "successful" status message (0x33 is TLV type for successful command status)
                tlv = new TLV(0x33, new byte[0]);
                data = tlv.getFullBuffer();
                writer.Write(data.Length);
                writer.Write(data);
            }
            catch (Exception e)
            {
                //Return exception error data (0x32 is TLV type for error data)
                byte[] exceptionBytes = Encoding.UTF8.GetBytes(e.Message);
                TLV tlv = new TLV(0x32, exceptionBytes);
                data = tlv.getFullBuffer();
                writer.Write(data.Length);
                writer.Write(data);
                writer.Flush();

                //Return the "error" status message(0x34 is TLV type for failed command status)
                tlv = new TLV(0x34, new byte[0]);
                data = tlv.getFullBuffer();
                writer.Write(data.Length);
                writer.Write(data);
            }

            //Close stuff up and wait 4sec just in case something is still being processed
            writer.Flush();
            client.WaitForPipeDrain();
            Thread.Sleep(4 * 1000);
            client.Close();
        }
    }
}
