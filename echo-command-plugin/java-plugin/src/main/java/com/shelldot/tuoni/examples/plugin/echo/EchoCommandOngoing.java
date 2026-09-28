package com.shelldot.tuoni.examples.plugin.echo;

import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandStatus;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnit;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitCommand;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultCollection;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultEditor;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.CommandUpdateUnsupportedException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ExecutionException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.Set;

public class EchoCommandOngoing implements ExecUnitCommand {

  private final AgentInfo agentInfo;
  private final EchoConfiguration echoConfiguration;

  public EchoCommandOngoing(
      int commandId,
      AgentInfo agentInfo,
      EchoConfiguration echoConfiguration,
      CommandContext commandContext) {
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
        getClass(), "echo-ongoing", type, pipeName, agentInfo.getLatestMetadata(),
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
  public void markStatus(CommandStatus status) {}

  @Override
  public void forceStop() throws ExecutionException {}
}
