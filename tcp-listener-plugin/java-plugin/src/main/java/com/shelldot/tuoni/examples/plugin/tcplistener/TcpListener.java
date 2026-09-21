package com.shelldot.tuoni.examples.plugin.tcplistener;

import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.PluginIpcType;
import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ExecutionException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.listener.Listener;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerContext;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerStatus;
import com.shelldot.tuoni.plugin.sdk.listener.ShellcodeListener;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadType;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.logging.Level;
import java.util.logging.Logger;

public class TcpListener implements ShellcodeListener {

  private static final Logger LOG = Logger.getLogger(TcpListener.class.getName());

  private static final String DEFAULT_PIPE_NAME = "QQQWWWEEE";
  private static final Charset PIPE_NAME_CHARSET = StandardCharsets.UTF_16LE;
  private static final String SHELLCODE_PATH = "/shellcodes/tcp-listener.shellcode";

  private final long listenerId;
  private final ListenerContext ctx;
  private TcpListenerPluginConfiguration config;

  private volatile ListenerStatus status = ListenerStatus.CREATED;
  private ServerSocket serverSocket;
  private Thread acceptThread;
  private ExecutorService workerPool;
  private final Set<Socket> activeSockets = ConcurrentHashMap.newKeySet();

  public TcpListener(
      long listenerId, TcpListenerPluginConfiguration config, ListenerContext ctx) {
    this.listenerId = listenerId;
    this.config = config;
    this.ctx = ctx;
  }

  @Override
  public String getInfo() {
    return "TCP listener on port " + config.port();
  }

  @Override
  public ListenerStatus getStatus() {
    return status;
  }

  @Override
  public synchronized void start() throws ExecutionException {
    if (status == ListenerStatus.STARTED) {
      return;
    }
    try {
      serverSocket = new ServerSocket(config.port());
    } catch (IOException e) {
      throw new ExecutionException("Failed to bind TCP listener on port " + config.port(), e);
    }
    workerPool = Executors.newCachedThreadPool();
    acceptThread = new Thread(this::acceptLoop, "tcp-listener-" + listenerId + "-accept");
    acceptThread.setDaemon(true);
    acceptThread.start();
    status = ListenerStatus.STARTED;
    LOG.info("TCP listener " + listenerId + " started on port " + config.port());
  }

  @Override
  public synchronized void stop() throws ExecutionException {
    if (status != ListenerStatus.STARTED) {
      return;
    }
    closeQuietly(serverSocket);
    serverSocket = null;
    for (Socket s : activeSockets) {
      try {
        s.close();
      } catch (IOException ignore) {
      }
    }
    activeSockets.clear();
    if (acceptThread != null) {
      acceptThread.interrupt();
      acceptThread = null;
    }
    if (workerPool != null) {
      workerPool.shutdownNow();
      workerPool = null;
    }
    status = ListenerStatus.STOPPED;
    LOG.info("TCP listener " + listenerId + " stopped");
  }

  @Override
  public synchronized void delete() throws ExecutionException {
    if (status == ListenerStatus.STARTED) {
      stop();
    }
    status = ListenerStatus.DELETED;
  }

  @Override
  public Listener reconfigure(Configuration newConfiguration)
      throws ExecutionException, SerializationException, ValidationException {
    TcpListenerPluginConfiguration newConfig =
        TcpListenerPluginConfiguration.fromConfiguration(newConfiguration);
    boolean wasStarted = status == ListenerStatus.STARTED;
    if (wasStarted) {
      stop();
    }
    this.config = newConfig;
    if (wasStarted) {
      start();
    }
    return this;
  }

  private void acceptLoop() {
    while (!Thread.currentThread().isInterrupted()
        && serverSocket != null
        && !serverSocket.isClosed()) {
      try {
        Socket socket = serverSocket.accept();
        activeSockets.add(socket);
        workerPool.submit(
            () ->
                new TcpConnectionHandler(listenerId, ctx, workerPool, socket, activeSockets::remove)
                    .run());
      } catch (IOException e) {
        if (serverSocket == null || serverSocket.isClosed()) {
          return;
        }
        LOG.log(Level.WARNING, "Accept failed on TCP listener " + listenerId, e);
      }
    }
  }

  @Override
  public Set<PayloadType> getSupportedPayloadTypes() {
    return Set.of(
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64),
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X86));
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, PayloadType payloadType)
      throws SerializationException {
    byte[] defaultPipeBytes = DEFAULT_PIPE_NAME.getBytes(PIPE_NAME_CHARSET);
    byte[] newPipeBytes = pipeName.getBytes(PIPE_NAME_CHARSET);

    ByteBuffer implantBuffer =
        ShellcodeUtil.readClasspathResourceToBuffer(getClass(), SHELLCODE_PATH);
    ShellcodeUtil.replaceBytesInBuffer(implantBuffer, defaultPipeBytes, newPipeBytes);

    return new ShellCodeWithConf(
        implantBuffer, config.serializeForShellcode(), PluginIpcType.NAMED_PIPE);
  }

  @Override
  public ByteBuffer serializeUpdatedConfiguration(Configuration configuration)
      throws SerializationException {
    return ByteBuffer.allocate(0);
  }

  private static void closeQuietly(ServerSocket s) {
    if (s != null) {
      try {
        s.close();
      } catch (IOException ignore) {
      }
    }
  }
}
