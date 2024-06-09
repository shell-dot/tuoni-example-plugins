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

            //Return same bytes back (0x30 is TLV type for "result data")
            TLV tlv = new TLV(0x30, data);
            data = tlv.getFullBuffer();
            writer.Write(data.Length);
            writer.Write(data);
            writer.Flush();

            //Return the "success" message
            tlv = new TLV(0x33, new byte[0]);
            data = tlv.getFullBuffer();
            writer.Write(data.Length);
            writer.Write(data);
            writer.Flush();

            //Close stuff up and wait 4sec just in case something is still being processed
            client.WaitForPipeDrain();
            Thread.Sleep(4 * 1000);
            client.Close();
        }
    }
}
