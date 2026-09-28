package com.shelldot.tuoni.examples.plugin.echo;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.manager.CommandOptions;
import com.shelldot.tuoni.plugin.sdk.job.Job;
import com.shelldot.tuoni.plugin.sdk.job.JobContext;
import com.shelldot.tuoni.plugin.sdk.job.JobMessage;
import com.shelldot.tuoni.plugin.sdk.job.JobResource;
import com.shelldot.tuoni.plugin.sdk.job.JobStatus;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.CommandInitializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import java.util.List;
import java.nio.ByteBuffer;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

public class EchoCommandOngoingMoreDataJob implements Job {
  private final CommandContext commandContext;
  private final int bindPort;
  private volatile JobContext jobContext;

  private EchoCommandOngoingMoreDataServer server;
  private Thread serverThread;

  public EchoCommandOngoingMoreDataJob(CommandContext commandContext, int bindPort) {
    this.bindPort = bindPort;
    this.commandContext = commandContext;
  }

  public void initServer() throws ValidationException {
    try {
      this.server = new EchoCommandOngoingMoreDataServer(this, bindPort);
      updateStatus(
            JobStatus.RUNNING,
            JobMessage.ofInfo("Started echo server at port=%d".formatted(bindPort)));
      serverThread = new Thread(this.server);
      serverThread.start();
    } catch (Exception e) {
      updateStatus(
          JobStatus.FAILED,
          JobMessage.ofError("Failed to start echo server at port=%d".formatted(bindPort), e));
    }
  }

  private void updateStatus(JobStatus status, JobMessage message) {
    Objects.requireNonNull(jobContext).updateJobStatus(status, message);
  }

  public void sendDataToCommand(ByteBuffer data) throws CommandInitializationException {
    commandContext.updateCommandWithFastTrack(data, CommandOptions.builder().build());
  }

  public void stopped() {
    updateStatus(
        JobStatus.FINISHED,
        JobMessage.ofInfo("Echo server at port=%d has stopped".formatted(bindPort)));
  }

  @Override
  public String getName() {
    return "Echo server";
  }

  @Override
  public List<? extends JobResource> getOpenResources() {
    return List.of();
  }

  @Override
  public void forceStop() {
    try {
      server.stop();
      serverThread.join(4000);
    } catch (InterruptedException e) {
      updateStatus(
          JobStatus.RUNNING,
          JobMessage.ofError(
              "Failed to stop echo server at port=%d".formatted(bindPort), e));
    }
  }

  @Override
  public boolean join(long timeout, TimeUnit timeUnit) {
    try {
      serverThread.join();
    return true;
    } catch (InterruptedException e) {
      return false;
    }
  }

  @Override
  public void init(long jobId, JobContext jobContext) {
    this.jobContext = jobContext;
  }
}
