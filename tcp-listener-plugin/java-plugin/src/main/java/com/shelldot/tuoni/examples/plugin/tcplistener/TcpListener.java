package com.shelldot.tuoni.examples.plugin.tcplistener;

import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.PluginIpcType;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnit;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ExecutionException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.listener.Listener;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerContext;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerStatus;
import com.shelldot.tuoni.plugin.sdk.listener.ExecUnitListener;
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

public class TcpListener implements ExecUnitListener {

  private static final Logger LOG = Logger.getLogger(TcpListener.class.getName());

  private static final String DEFAULT_PIPE_NAME = "QQQWWWEEE";
  private static final Charset PIPE_NAME_CHARSET = StandardCharsets.UTF_16LE;
  private static final String WINDOWS_SHELLCODE_PATH = "/shellcodes/tcp-listener.shellcode";
  private static final String LINUX_EXECUNIT_PATH = "/shellcodes/tcp-listener-linux.native64_so";
  private static final PayloadType LINUX_X64 =
      PayloadType.of(OperatingSystem.LINUX, Architecture.X64);

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
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X86),
        LINUX_X64);
  }

  @Override
  public Set<ExecUnitType> getSupportedExecUnitTypes(PayloadType payloadType) {
    if (payloadType == null) {
      return Set.of();
    }
    if (LINUX_X64.equals(payloadType)) {
      return Set.of(ExecUnitType.NATIVE_LIB);
    }
    if (getSupportedPayloadTypes().contains(payloadType)) {
      return Set.of(ExecUnitType.SHELLCODE_NATIVE, ExecUnitType.DOTNET_DLL,
            ExecUnitType.DOTNET_EXE, ExecUnitType.NATIVE_LIB);
    }
    return Set.of();
  }

  @Override
  public ExecUnit generateExecUnit(ExecUnitType type, String pipeName, PayloadType payloadType)
      throws SerializationException {
    if (!getSupportedExecUnitTypes(payloadType).contains(type)) {
      throw new SerializationException(
          "Unsupported execution unit type " + type + " for payload type " + payloadType);
    }
    String resource = switch (type) {
      case SHELLCODE_NATIVE -> WINDOWS_SHELLCODE_PATH;
      case DOTNET_DLL -> "/shellcodes/tcp-listener.dotnet_dll";
      case DOTNET_EXE -> "/shellcodes/tcp-listener.dotnet_exe";
      case NATIVE_LIB -> payloadType.operatingSystem() == OperatingSystem.WINDOWS
          ? (payloadType.architecture() == Architecture.X86
              ? "/shellcodes/tcp-listener.native32_dll" : "/shellcodes/tcp-listener.native64_dll")
          : LINUX_EXECUNIT_PATH;
    };
    ByteBuffer implantBuffer = ShellcodeUtil.readClasspathResourceToBuffer(
        getClass(), resource);
    if (type == ExecUnitType.SHELLCODE_NATIVE) {
      if (pipeName == null) {
        throw new SerializationException("Pipe name is missing");
      }
      byte[] defaultPipeBytes = DEFAULT_PIPE_NAME.getBytes(PIPE_NAME_CHARSET);
      byte[] newPipeBytes = pipeName.getBytes(PIPE_NAME_CHARSET);
      ShellcodeUtil.replaceBytesInBuffer(implantBuffer, defaultPipeBytes, newPipeBytes);
    }

    return ExecUnit.builder()
        .code(implantBuffer)
        .type(type)
        .ipcType(PluginIpcType.NAMED_PIPE)
        .configuration(config.serializeForShellcode())
        .entrypoint(switch (type) {
          case DOTNET_DLL -> ShellcodeUtil.dllEntrypoint(getClass(), resource);
          case NATIVE_LIB -> payloadType.operatingSystem() == OperatingSystem.WINDOWS ? "start" : "run";
          default -> null;
        })
        .build();
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
