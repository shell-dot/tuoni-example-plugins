using ExecUnitUtils;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace CommandEchoFile
{
    internal class Program
    {
        static void Main(string[] args)
        {
            bool active = true;

            //Creating connection to the named pipe listener in agent (QQQWWWEEE is likely overwritten in reality)
            CommunicationNamedPipesCommand client = new CommunicationNamedPipesCommand("QQQWWWEEE", 
                null, 
                delegate(){ active = false; }  // This is ran when command is stopped by user
                );
            byte[] confData = client.Connect();


            //Configuration
            MemoryStream ms = new MemoryStream(confData);
            BinaryReader reader = new BinaryReader(ms);

            int lines = reader.ReadInt32();
            string[] msgs = Encoding.UTF8.GetString(confData, 4, confData.Length - 4).Split('\n');

            //Result will be ongoing
            client.sendConf_ongoingResult();

            //Result can stop itself
            client.sendConf_stopWait(10 * 1000); //Wait max 10sec before stopping by force

            try
            {
                //Send back the lines with delay
                int lineIdx = 0;
                while (lineIdx < msgs.Length)
                {
                    client.sendResult(Encoding.UTF8.GetBytes($"{msgs[lineIdx++]}\n"));
                    if(lineIdx % lines == 0)
                        Thread.Sleep(1000);
                    if(!active)
                    {
                        client.sendResult(Encoding.UTF8.GetBytes($"=== USER FORCED STOP ===\n"));
                        break;
                    }
                }
                client.sendResult(Encoding.UTF8.GetBytes($"Stopping now\n"));

                //Return the "successful" status message
                client.sendReturnSuccess();
            }
            catch (Exception e)
            {
                //Return exception error message
                client.sendError(Encoding.UTF8.GetBytes(e.Message));

                //Return the "error" status message
                client.sendReturnFailed();
            }

            //Wait 4sec just in case something is still being processed
            Thread.Sleep(4 * 1000);
            client.Close();
        }
    }
}
