package com.shelldot.tuoni.examples.plugin.echo;

import com.shelldot.tuoni.examples.plugin.echo.utils.ShellcodeUtil;
import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandStatus;
import com.shelldot.tuoni.plugin.sdk.command.ShellcodeCommand;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultCollection;
import com.shelldot.tuoni.plugin.sdk.command.result.CommandResultEditor;
import com.shelldot.tuoni.plugin.sdk.common.AgentMetadata;
import com.shelldot.tuoni.plugin.sdk.common.PluginIpcType;
import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.CommandUpdateUnsupportedException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ExecutionException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import java.nio.ByteBuffer;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

public class EchoCommand implements ShellcodeCommand {

  private static final String DEFAULT_PIPE_NAME = "QQQWWWEEE";
  private static final String SHELLCODE_PATH = "/shellcode/CommandEcho.shellcode";

  private final int commandId;
  private final AgentInfo agentInfo;
  private final EchoConfiguration echoConfiguration;
  private final CommandContext commandContext;

  public EchoCommand(
      int commandId,
      AgentInfo agentInfo,
      EchoConfiguration echoConfiguration,
      CommandContext commandContext) {
    this.commandId = commandId;
    this.agentInfo = agentInfo;
    this.echoConfiguration = echoConfiguration;
    this.commandContext = commandContext;
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, AgentMetadata latestAgentMetadata)
      throws SerializationException, ValidationException {
    Charset pipeNameCharset = StandardCharsets.UTF_16LE;
    byte[] defaultPipeBytes = DEFAULT_PIPE_NAME.getBytes(pipeNameCharset);
    byte[] newPipeBytes = pipeName.getBytes(pipeNameCharset);

    ByteBuffer implantBuffer =
        ShellcodeUtil.readClasspathResourceToBuffer(getClass(), SHELLCODE_PATH);
    ShellcodeUtil.replaceBytesInBuffer(implantBuffer, defaultPipeBytes, newPipeBytes);

    return new ShellCodeWithConf(
        implantBuffer, echoConfiguration.serializeForShellcode(), PluginIpcType.NAMED_PIPE);
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
