package com.shelldot.tuoni.examples.plugin.echo;

import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandStatus;
import com.shelldot.tuoni.plugin.sdk.command.ShellcodeCommand;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultCollection;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultEditor;
import com.shelldot.tuoni.plugin.sdk.common.AgentMetadata;
import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.CommandUpdateUnsupportedException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ExecutionException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.job.source.CommandJobSource;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;

public class EchoCommandOngoingMoreData implements ShellcodeCommand {

  private final EchoConfigurationOngoingMoreData echoConfiguration;
  private final EchoCommandOngoingMoreDataJob echoJob;

  public EchoCommandOngoingMoreData(
      int commandId,
      AgentInfo agentInfo,
      EchoConfigurationOngoingMoreData echoConfiguration,
      CommandContext commandContext) throws ValidationException {
    this.echoConfiguration = echoConfiguration;
    this.echoJob = new EchoCommandOngoingMoreDataJob(commandContext, echoConfiguration.port());
    commandContext
        .getPluginContext()
        .getJobManager()
        .registerJob(this.echoJob, new CommandJobSource(commandId));
    this.echoJob.initServer();
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, AgentMetadata latestAgentMetadata)
      throws SerializationException, ValidationException {
    return EchoPayloads.generate(
        getClass(), "echo-ongoing-more-data", pipeName, latestAgentMetadata,
        echoConfiguration.serializeForShellcode());
  }

  @Override
  public void parseResult(
      ByteBuffer buffer,
      boolean isFinalResult,
      CommandResultCollection previousResult,
      CommandResultEditor editor)
      throws SerializationException {
    if (buffer.remaining() > 0 || previousResult != null) {
      String resultString = StandardCharsets.UTF_8.decode(buffer).toString();
      editor.appendTextResult("STDOUT", resultString);
    }
    editor.commit();
  }

  @Override
  public ByteBuffer serializeCommandUpdate(Configuration updateConfiguration)
      throws SerializationException, ValidationException, CommandUpdateUnsupportedException {
    throw CommandUpdateUnsupportedException.forTemplateName(EchoCommandTemplate.NAME);
  }

  @Override
  public void markStatus(CommandStatus status) {
    switch (status) {
      case COMPLETE, FAILED -> echoJob.forceStop();
    }
  }

  @Override
  public void forceStop() throws ExecutionException {}  

  @Override
  public void notifyAgentChanged(AgentInfo agentInfo) {
    if (!agentInfo.isActive()) {
      echoJob.forceStop();
    }
  }
}
