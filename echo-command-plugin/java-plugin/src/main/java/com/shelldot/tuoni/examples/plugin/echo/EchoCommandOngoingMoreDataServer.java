package com.shelldot.tuoni.examples.plugin.echo;

import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.manager.CommandOptions;

public class EchoCommandOngoingMoreDataServer implements Runnable {
  private EchoCommandOngoingMoreDataJob job;
  private Socket client;
  private ServerSocket serverSocket;

  EchoCommandOngoingMoreDataServer(EchoCommandOngoingMoreDataJob job, int port) throws IOException {
    this.job = job;
    this.serverSocket = new ServerSocket(port);
  }

  public void stop() {
    if (client != null && !client.isClosed())
    {
      try
      {
        client.close();
      }
      catch(IOException e){}
    }
    if (serverSocket != null && !serverSocket.isClosed())
    {
      try
      {
        serverSocket.close();
      }
      catch(IOException e){}
    }
  }

  @Override
  public void run() {
    try {
      client = this.serverSocket.accept();
      BufferedReader in = new BufferedReader(
          new InputStreamReader(client.getInputStream(), StandardCharsets.UTF_8));

      String line;
      while ((line = in.readLine()) != null) {
        job.sendDataToCommand(ByteBuffer.wrap(line.getBytes(StandardCharsets.UTF_8)));
      }
    } catch (Exception e) { 
    } finally {
      try
      {
        job.sendDataToCommand(ByteBuffer.allocate(1)); // Indicate end of data with a single 0 byte
      }
      catch (Exception e) { }
      stop();
      job.stopped();
    }
  }
}
