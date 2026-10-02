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
    // This object represents one invocation, identified by commandId; parsing buffers,
    // cancellation state and owned resources must not be shared across invocations.
    // Store an immutable typed configuration produced by the same parser used by
    // validateConfiguration, plus commandContext only if the implementation needs it.
    // Copy/read uploaded input while its lifetime is valid, and establish cleanup
    // ownership before acquiring resources that forceStop or status changes release.
  }

  @Override
  public Set<ExecUnitType> getSupportedExecUnitTypes() {
    // Report only execution formats available for this invocation's latest agent
    // metadata. Keep this selection consistent with the template's compatibility
    // check and the resource/entrypoint guards in both generation methods.
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
    // The code resource is the executable artifact; configuration is a separate
    // inner payload decoded by the Windows Initialize/Linux run implementation.
    // Replace the empty buffer with the validated configuration's shared encoder
    // when fields are added; use the same bytes as generateShellCode and return a
    // fresh buffer at position zero with an exact limit. The SDK adds host framing.
    // Keep Linux's run export and Windows's patched pipe name aligned with the
    // packaged artifact; reject unavailable OS/process-architecture/type combinations.
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
    // This is the shellcode delivery path for the same invocation, not a second
    // configuration format. Replace the empty buffer with the same encoder used by
    // generateExecUnit, preserving independent readable buffer positions. pipeName
    // is patched into the Windows resource; it must match the placeholder's encoded
    // length. Report resource/encoding failures as SerializationException.
    return new ShellCodeWithConf(
        ShellcodeResource.load(getClass(), SHELLCODE_RESOURCE, pipeName),
        ByteBuffer.allocate(0),
        PluginIpcType.NAMED_PIPE);
  }

  private static Set<ExecUnitType> supportedTypes(AgentMetadata metadata) {
    // Match the agent process architecture to artifacts actually built and packaged;
    // the OS architecture alone cannot prove that an artifact can run in the process.
    // Linux currently has only an x64 library. The Windows OS-only scaffold branch
    // needs explicit architecture guards once the shellcode's supported set is known.
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
    // buffer contains only the native sendResult payload, with the host pipe envelope
    // already removed. Decode the format agreed with every native sender and validate
    // lengths, text encodings and record structure before publishing editor changes.
    // Use stable result names and the appropriate text/binary/file editor APIs, then
    // commit changes. previousResult supplies earlier published values; append or merge
    // chunks instead of overwriting them, retaining incomplete records per invocation.
    // isFinalResult can arrive with an empty buffer: finish any accumulator and reject
    // truncated data then. It does not itself indicate native success or failure.
    // Throw SerializationException for malformed payloads, without committing a
    // partially decoded update. See docs/output.md for editor and streaming contracts.
    throw new SerializationException("TODO: Implement command result parsing.");
  }

  @Override
  public ByteBuffer serializeCommandUpdate(Configuration updateConfiguration)
      throws SerializationException, ValidationException, CommandUpdateUnsupportedException {
    // Optional: Replace this if the command accepts updates while running.
    // Validate updateConfiguration with explicit patch/replacement semantics and
    // encode only the agreed inner update payload. The native update callback must
    // decode that representation and apply a valid candidate atomically. Return a
    // fresh buffer at position zero; use ValidationException for invalid fields and
    // SerializationException for encoding errors. Keep this exception when updates
    // are unsupported rather than accepting an update that native code ignores.
    throw CommandUpdateUnsupportedException.forTemplateName(TemplateCommandTemplate.NAME);
  }

  @Override
  public void markStatus(CommandStatus status) {
    // TODO: Handle status changes if the command maintains state.
    // The host reports lifecycle transitions through status. Track them only when
    // this invocation needs them, releasing server-side state on terminal transitions
    // and tolerating repeated notifications. This hook does not send the native
    // command's terminal IPC message. A command with no owned state can leave it empty.
  }

  @Override
  public void forceStop() throws ExecutionException {
    // TODO: Release any resources owned by this command.
    // Stop work and release resources owned by this Java invocation when the host
    // requests a forced stop. Make cleanup safe after partial initialization and
    // repeated calls, and coordinate it with parsing/status callbacks. Unblock and
    // await owned Java workers before discarding their state; surface an actual stop
    // failure as ExecutionException. Native cancellation and unload cleanup must
    // also be implemented in the exec-unit; this method cannot replace that lifecycle.
    // Server-side cleanup does not prove the agent stopped; later parseResult calls
    // may still arrive. Define whether they are ignored or recreate released Java state.
  }
}
