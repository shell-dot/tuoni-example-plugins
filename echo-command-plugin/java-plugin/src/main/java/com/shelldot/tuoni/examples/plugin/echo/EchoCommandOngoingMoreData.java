package com.shelldot.tuoni.examples.plugin.echo;

import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandStatus;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnit;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitCommand;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
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
import java.util.Set;

public class EchoCommandOngoingMoreData implements ExecUnitCommand, ShellcodeCommand {

  private final AgentInfo agentInfo;
  private final EchoConfigurationOngoingMoreData echoConfiguration;
  private final EchoCommandOngoingMoreDataJob echoJob;

  public EchoCommandOngoingMoreData(
      int commandId,
      AgentInfo agentInfo,
      EchoConfigurationOngoingMoreData echoConfiguration,
      CommandContext commandContext) throws ValidationException {
    this.agentInfo = agentInfo;
    this.echoConfiguration = echoConfiguration;
    this.echoJob = new EchoCommandOngoingMoreDataJob(commandContext, echoConfiguration.port());
    commandContext
        .getPluginContext()
        .getJobManager()
        .registerJob(this.echoJob, new CommandJobSource(commandId));
    this.echoJob.initServer();
  }

  @Override
  public Set<ExecUnitType> getSupportedExecUnitTypes() {
    return EchoPayloads.supportedTypes(agentInfo.getLatestMetadata());
  }

  @Override
  public ExecUnit generateExecUnit(ExecUnitType type, String pipeName)
      throws SerializationException, ValidationException {
    return EchoPayloads.generate(
        getClass(), "echo-ongoing-more-data", type, pipeName, agentInfo.getLatestMetadata(),
        echoConfiguration.serializeForShellcode());
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, AgentMetadata latestAgentMetadata)
      throws SerializationException, ValidationException {
    return EchoPayloads.generateShellCode(
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
