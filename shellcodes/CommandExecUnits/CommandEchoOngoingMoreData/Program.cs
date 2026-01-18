using ExecUnitUtils;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace CommandEchoOngoingMoreData
{
    internal class Program
    {
        static CommunicationNamedPipesCommand client = null;
        static EventWaitHandle stopEvent = new EventWaitHandle(false, EventResetMode.AutoReset);
        static bool error = false;

        static void serverSentNewData(byte[] data)
        {
            //If no data or first byte is null, stop the command
            if (data == null || data.Length == 0 || (data.Length == 1 && data[0] == 0))
            {
                stop();
                return;
            }

            //Echoing back the new data or error
            try
            {
                string msg = Encoding.UTF8.GetString(data);
                client.sendResult(Encoding.UTF8.GetBytes($"New data: {msg}\n"));
            }
            catch (Exception e)
            {
                try
                {
                    client.sendError(Encoding.UTF8.GetBytes(e.Message));
                    error = true;
                    stop();
                }
                catch (Exception) { }
            }
        }
        static void stop()
        {
            stopEvent.Set();
        }

        static void Main(string[] args)
        {
            try
            {
                //Creating connection to the named pipe listener in agent (QQQWWWEEE is likely overwritten in reality) and setting callbacks
                client = new CommunicationNamedPipesCommand("QQQWWWEEE", newData => { serverSentNewData(newData); }, () => { stop(); });
                byte[] confData = client.Connect();

                //Setting command ongoing
                client.sendConf_ongoingResult();

                //Setting stop wait time to 10sec before agent forcefully stops it
                client.sendConf_stopWait(10 * 1000);

                //Initial data
                string msg = Encoding.UTF8.GetString(confData);
                client.sendResult(Encoding.UTF8.GetBytes($"Initial data: {msg}\n"));

                //Waiting until stop is requested
                stopEvent.WaitOne();

                //Finish the command
                if(error)
                    client.sendReturnFailed();
                else
                    client.sendReturnSuccess();

                //Wait 4sec just in case something is still being processed
                Thread.Sleep(4 * 1000);
                client.Close();
            }
            catch (Exception){ }
        }
    }
}
