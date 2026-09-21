namespace DotNetAgent
{
    internal class ListenerManager
    {
        private static Listener _singleListener;

        public static Listener LoadListener(TLV tlv)
        {
            if (_singleListener != null)
            {
                Logger.Warning("Can't load listener because we already have one");
                return null;
            }
            Listener listener = new Listener();
            if (!listener.Load(tlv))
            {
                Logger.Warning("Can't load listener because its conf is bad");
                return null;
            }
            _singleListener = listener;
            return listener;
        }

        public static bool StartSingleListener()
        {
            if (_singleListener == null)
            {
                return false;
            }
            return _singleListener.Start();
        }

        public static void SendMessageToSingleListener(byte[] message)
        {
            if (_singleListener == null)
            {
                Logger.Warning("Can't send message to listener because we don't have one");
                return;
            }
            _singleListener.SendMessage(message);
        }
    }
}
