package com.shelldot.tuoni.examples.plugin.echo;

import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
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
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.Set;

public class EchoCommand implements ExecUnitCommand, ShellcodeCommand {

  private final AgentInfo agentInfo;
  private final EchoConfiguration echoConfiguration;

  public EchoCommand(AgentInfo agentInfo, EchoConfiguration echoConfiguration) {
    this.agentInfo = agentInfo;
    this.echoConfiguration = echoConfiguration;
  }

  @Override
  public Set<ExecUnitType> getSupportedExecUnitTypes() {
    return EchoPayloads.supportedTypes(agentInfo.getLatestMetadata());
  }

  @Override
  public ExecUnit generateExecUnit(ExecUnitType type, String pipeName)
      throws SerializationException, ValidationException {
    return EchoPayloads.generate(
        getClass(), "echo", type, pipeName, agentInfo.getLatestMetadata(),
        echoConfiguration.serializeForShellcode());
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, AgentMetadata latestAgentMetadata)
      throws SerializationException, ValidationException {
    return EchoPayloads.generateShellCode(
        getClass(), "echo", pipeName, latestAgentMetadata,
        echoConfiguration.serializeForShellcode());
  }

  @Override
  public void parseResult(
      ByteBuffer buffer,
      boolean isFinalResult,
      CommandResultCollection previousResult,
      CommandResultEditor editor)
      throws SerializationException {
    String receivedString = StandardCharsets.UTF_8.decode(buffer).toString();
    editor.setTextResult("message", receivedString);
    editor.commit();
  }

  @Override
  public ByteBuffer serializeCommandUpdate(Configuration updateConfiguration)
      throws SerializationException, ValidationException, CommandUpdateUnsupportedException {
    throw CommandUpdateUnsupportedException.forTemplateName(EchoCommandTemplate.NAME);
  }

  @Override
  public void markStatus(CommandStatus status) {}

  @Override
  public void forceStop() throws ExecutionException {}
}
