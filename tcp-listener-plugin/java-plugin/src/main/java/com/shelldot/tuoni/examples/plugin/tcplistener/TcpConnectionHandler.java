package com.shelldot.tuoni.examples.plugin.tcplistener;

import com.shelldot.tuoni.plugin.sdk.common.AgentMetadata;
import com.shelldot.tuoni.plugin.sdk.listener.Agent;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerContext;
import com.shelldot.tuoni.plugin.sdk.listener.SendStatus;
import com.shelldot.tuoni.plugin.sdk.listener.SerializedCommand;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.time.Instant;
import java.util.Optional;
import java.util.function.Consumer;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;

final class TcpConnectionHandler {

  private static final Logger LOG = Logger.getLogger(TcpConnectionHandler.class.getName());

  private static final long COMMAND_POLL_TIMEOUT_SECONDS = 1L;

  private final long listenerId;
  private final ListenerContext ctx;
  private final ExecutorService workerPool;
  private final Socket socket;
  private final Consumer<Socket> onClose;

  TcpConnectionHandler(
      long listenerId,
      ListenerContext ctx,
      ExecutorService workerPool,
      Socket socket,
      Consumer<Socket> onClose) {
    this.listenerId = listenerId;
    this.ctx = ctx;
    this.workerPool = workerPool;
    this.socket = socket;
    this.onClose = onClose;
  }

  void run() {
    final Object streamLock = new Object();
    final String remoteAddress = String.valueOf(socket.getRemoteSocketAddress());
    try (Socket s = socket;
        InputStream in = s.getInputStream();
        OutputStream out = s.getOutputStream()) {

      Agent agent = null;
      while (!s.isClosed()) {
        int metaLen = TcpFrameCodec.readLeInt(in);
        byte[] metaBytes = TcpFrameCodec.readFully(in, metaLen);
        int dataLen = TcpFrameCodec.readLeInt(in);
        byte[] dataBytes = TcpFrameCodec.readFully(in, dataLen);

        Optional<AgentMetadata> metadataOpt = ctx.readMetadata(ByteBuffer.wrap(metaBytes));
        if (metadataOpt.isEmpty()) {
          LOG.warning(
              "Listener " + listenerId + ": failed to parse agent metadata from " + remoteAddress);
          return;
        }
        AgentMetadata metadata = metadataOpt.get();

        if (agent == null) {
          agent = resolveOrRegisterAgent(metadata);
          startCommandPusher(agent, out, streamLock, s, remoteAddress);
        }

        if (dataLen > 0) {
          agent.submitSerializedRequest(metadata, ByteBuffer.wrap(dataBytes)).join();
        }
      }
    } catch (IOException e) {
      LOG.log(Level.FINE, "Listener " + listenerId + ": connection closed (" + remoteAddress + ")", e);
    } catch (Exception e) {
      LOG.log(
          Level.WARNING,
          "Listener " + listenerId + ": error handling connection from " + remoteAddress,
          e);
    } finally {
      onClose.accept(socket);
    }
  }

  private Agent resolveOrRegisterAgent(AgentMetadata metadata) {
    return ctx.findRegisteredAgent(metadata.guid())
        .orElseGet(
            () -> {
              try {
                return ctx.registerAgent(metadata.guid(), metadata);
              } catch (Exception e) {
                throw new RuntimeException(
                    "Failed to register agent " + metadata.guid() + " on listener " + listenerId, e);
              }
            });
  }

  private void startCommandPusher(
      Agent agent, OutputStream out, Object streamLock, Socket s, String remoteAddress) {
    workerPool.submit(
        () -> {
          try {
            while (!s.isClosed()) {
              Optional<SerializedCommand> commandOpt =
                  agent.getCommandQueue().pollCommand(COMMAND_POLL_TIMEOUT_SECONDS, TimeUnit.SECONDS);
              if (commandOpt.isEmpty()) {
                continue;
              }
              SerializedCommand command = commandOpt.get();
              ByteBuffer payload = command.getSerializedBytes();
              byte[] bytes = new byte[payload.remaining()];
              payload.get(bytes);
              try {
                synchronized (streamLock) {
                  TcpFrameCodec.writeLeInt(out, bytes.length);
                  out.write(bytes);
                  out.flush();
                }
                command.setSendStatus(SendStatus.successful(Instant.now()));
              } catch (IOException e) {
                command.setSendStatus(SendStatus.failure(e, Instant.now(), true));
                return;
              }
            }
          } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
          } catch (Exception e) {
            LOG.log(
                Level.WARNING,
                "Listener " + listenerId + ": command pusher failed for " + remoteAddress,
                e);
          }
        });
  }
}
