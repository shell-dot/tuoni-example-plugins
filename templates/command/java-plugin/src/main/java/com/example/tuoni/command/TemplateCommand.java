package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandStatus;
import com.shelldot.tuoni.plugin.sdk.command.ShellcodeCommand;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultCollection;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultEditor;
import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.common.AgentMetadata;
import com.shelldot.tuoni.plugin.sdk.common.PluginIpcType;
import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.CommandUpdateUnsupportedException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ExecutionException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import java.nio.ByteBuffer;

public class TemplateCommand implements ShellcodeCommand {

  private static final String SHELLCODE_RESOURCE = "/command.shellcode";

  public TemplateCommand(
      int commandId,
      AgentInfo agentInfo,
      Configuration configuration,
      CommandContext commandContext) {
    // TODO: Retain the validated configuration and context needed by this command.
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, AgentMetadata latestAgentMetadata)
      throws SerializationException, ValidationException {
    return new ShellCodeWithConf(
        ShellcodeResource.load(getClass(), SHELLCODE_RESOURCE, pipeName),
        ByteBuffer.allocate(0),
        PluginIpcType.NAMED_PIPE);
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
