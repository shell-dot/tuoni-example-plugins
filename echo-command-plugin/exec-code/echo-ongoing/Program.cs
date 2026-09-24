using ExecUnitUtils;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace CommandEchoOngoing
{
    internal class Program
    {
        static void Main(string[] args)
        {
            //Creating connection to the named pipe listener in agent (QQQWWWEEE is likely overwritten in reality)
            CommunicationNamedPipesCommand client = new CommunicationNamedPipesCommand("QQQWWWEEE", null, null);
            byte[] confData = client.Connect();
            string msg = Encoding.UTF8.GetString(confData);

            //Result will be ongoing
            client.sendConf_ongoingResult();

            try
            {
                for(int counter = 0; counter < 4; counter++)
                {
                    //Return same bytes back as data with newline and wait 1sec
                    client.sendResult(Encoding.UTF8.GetBytes($"{counter}: {msg}\n"));
                    Thread.Sleep(1000);
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
