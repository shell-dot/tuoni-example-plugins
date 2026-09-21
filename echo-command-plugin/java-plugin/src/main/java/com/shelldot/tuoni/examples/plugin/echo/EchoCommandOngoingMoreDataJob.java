package com.shelldot.tuoni.examples.plugin.echo;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.manager.CommandOptions;
import com.shelldot.tuoni.plugin.sdk.job.Job;
import com.shelldot.tuoni.plugin.sdk.job.JobAction;
import com.shelldot.tuoni.plugin.sdk.job.JobContext;
import com.shelldot.tuoni.plugin.sdk.job.JobMessage;
import com.shelldot.tuoni.plugin.sdk.job.JobResource;
import com.shelldot.tuoni.plugin.sdk.job.JobStatus;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.CommandInitializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.common.validation.ValidationViolation;
import com.shelldot.tuoni.plugin.sdk.common.validation.ValidationViolation.ViolationType;
import java.util.List;
import java.io.IOException;
import java.net.BindException;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
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
  public Set<JobAction> getSupportedActions() {
    return switch (Objects.requireNonNull(jobContext).getCurrentStatus()) {
      case INITIALIZING, RUNNING, MANUALLY_PAUSED, AUTOMATICALLY_PAUSED, FINISHED, FAILED -> Set.of();
    };
  }

  @Override
  public List<? extends JobResource> getOpenResources() {
    return new ArrayList<>();
  }

  @Override
  public void pause() {
  }

  @Override
  public void restart() {
  }

  @Override
  public void resume() {
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
