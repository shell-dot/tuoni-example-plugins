using ExecUnitUtils;
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
            CommunicationNamedPipesCommand client = new CommunicationNamedPipesCommand("QQQWWWEEE", null, null);
            byte[] confData = client.Connect();

            try
            {
                //To show error handling
                String confString = Encoding.UTF8.GetString(confData);
                if(confString.StartsWith("ERR:"))
                    throw new Exception("Simulated exception: " + confString.Substring(4));

                //Return same bytes back as data
                client.sendResult(confData);

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
