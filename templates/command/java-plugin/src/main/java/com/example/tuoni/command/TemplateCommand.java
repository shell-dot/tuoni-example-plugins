package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandStatus;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnit;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitCommand;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
import com.shelldot.tuoni.plugin.sdk.command.ShellcodeCommand;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultCollection;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultEditor;
import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.common.AgentMetadata;
import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.PluginIpcType;
import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.CommandUpdateUnsupportedException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ExecutionException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import java.nio.ByteBuffer;
import java.util.Set;

public class TemplateCommand implements ExecUnitCommand, ShellcodeCommand {

  private static final String SHELLCODE_RESOURCE = "/command.shellcode";
  private static final String LINUX_RESOURCE = "/command-linux.native64_so";
  private final AgentInfo agentInfo;

  public TemplateCommand(
      int commandId,
      AgentInfo agentInfo,
      Configuration configuration,
      CommandContext commandContext) {
    this.agentInfo = agentInfo;
    // TODO: Retain the validated configuration and context needed by this command.
  }

  @Override
  public Set<ExecUnitType> getSupportedExecUnitTypes() {
    return supportedTypes(agentInfo.getLatestMetadata());
  }

  @Override
  public ExecUnit generateExecUnit(ExecUnitType type, String pipeName)
      throws SerializationException, ValidationException {
    AgentMetadata metadata = agentInfo.getLatestMetadata();
    if (!supportedTypes(metadata).contains(type)) {
      throw new SerializationException(
          "Unsupported execution unit type " + type + " for agent " + metadata);
    }
    boolean linux = metadata.os() == OperatingSystem.LINUX;
    return ExecUnit.builder()
        .code(linux
            ? ShellcodeResource.read(getClass(), LINUX_RESOURCE)
            : ShellcodeResource.load(getClass(), SHELLCODE_RESOURCE, pipeName))
        .type(type)
        .ipcType(PluginIpcType.NAMED_PIPE)
        .configuration(ByteBuffer.allocate(0))
        .entrypoint(linux ? "run" : null)
        .build();
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, AgentMetadata latestAgentMetadata)
      throws SerializationException, ValidationException {
    if (!supportedTypes(latestAgentMetadata).contains(ExecUnitType.SHELLCODE_NATIVE)) {
      throw new SerializationException("Unsupported shellcode agent: " + latestAgentMetadata);
    }
    return new ShellCodeWithConf(
        ShellcodeResource.load(getClass(), SHELLCODE_RESOURCE, pipeName),
        ByteBuffer.allocate(0),
        PluginIpcType.NAMED_PIPE);
  }

  private static Set<ExecUnitType> supportedTypes(AgentMetadata metadata) {
    if (metadata == null) {
      return Set.of();
    }
    return switch (metadata.os()) {
      case WINDOWS -> Set.of(ExecUnitType.SHELLCODE_NATIVE);
      case LINUX -> metadata.processArch() == Architecture.X64
          ? Set.of(ExecUnitType.NATIVE_LIB) : Set.of();
      default -> Set.of();
    };
  }

  @Override
  public void parseResult(
      ByteBuffer buffer,
      boolean isFinalResult,
      CommandResultCollection previousResult,
      CommandResultEditor editor)
      throws SerializationException {
    // TODO: Define result decoding and update the result editor.
    throw new SerializationException("TODO: Implement command result parsing.");
  }

  @Override
  public ByteBuffer serializeCommandUpdate(Configuration updateConfiguration)
      throws SerializationException, ValidationException, CommandUpdateUnsupportedException {
    // Optional: Replace this if the command accepts updates while running.
    throw CommandUpdateUnsupportedException.forTemplateName(TemplateCommandTemplate.NAME);
  }

  @Override
  public void markStatus(CommandStatus status) {
    // TODO: Handle status changes if the command maintains state.
  }

  @Override
  public void forceStop() throws ExecutionException {
    // TODO: Release any resources owned by this command.
  }
}
