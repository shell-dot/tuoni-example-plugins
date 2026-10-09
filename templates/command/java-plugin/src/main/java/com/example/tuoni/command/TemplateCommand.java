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
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
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
    // This no-op command has no configuration fields or owned resources. Retain an
    // immutable typed configuration/context here when adding command behavior.
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
    String resource = switch (type) {
      case SHELLCODE_NATIVE -> SHELLCODE_RESOURCE;
      case DOTNET_DLL -> "/command.dotnet_dll";
      case DOTNET_EXE -> "/command.dotnet_exe";
      case NATIVE_LIB -> metadata.os() == OperatingSystem.WINDOWS
          ? (metadata.processArch() == Architecture.X86
              ? "/command.native32_dll" : "/command.native64_dll")
          : LINUX_RESOURCE;
    };
    // The code resource is the executable artifact; configuration is a separate
    // inner payload decoded by the Windows Initialize/Linux run implementation.
    // Extend the shared configuration encoder when fields are added; use the same
    // bytes as generateShellCode and return a
    // fresh buffer at position zero with an exact limit. The SDK adds host framing.
    // Keep Linux's run export and Windows's start export/managed arguments/shellcode patch aligned with the
    // packaged artifact; reject unavailable OS/process-architecture/type combinations.
    return ExecUnit.builder()
        .code(type == ExecUnitType.SHELLCODE_NATIVE
            ? ShellcodeResource.load(getClass(), resource, pipeName)
            : ShellcodeResource.read(getClass(), resource))
        .type(type)
        .ipcType(PluginIpcType.NAMED_PIPE)
        .configuration(serializeConfiguration())
        .entrypoint(switch (type) {
          case DOTNET_DLL -> ShellcodeResource.dllEntrypoint(getClass(), resource);
          case NATIVE_LIB -> metadata.os() == OperatingSystem.WINDOWS ? "start" : "run";
          default -> null;
        })
        .build();
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, AgentMetadata latestAgentMetadata)
      throws SerializationException, ValidationException {
    if (!supportedTypes(latestAgentMetadata).contains(ExecUnitType.SHELLCODE_NATIVE)) {
      throw new SerializationException("Unsupported shellcode agent: " + latestAgentMetadata);
    }
    // This is the shellcode delivery path for the same invocation, not a second
    // configuration format. Keep the shared encoder used by generateExecUnit,
    // preserving independent readable buffer positions. pipeName
    // is patched into the Windows resource; it must match the placeholder's encoded
    // length. Report resource/encoding failures as SerializationException.
    return new ShellCodeWithConf(
        ShellcodeResource.load(getClass(), SHELLCODE_RESOURCE, pipeName),
        serializeConfiguration(),
        PluginIpcType.NAMED_PIPE);
  }

  private ByteBuffer serializeConfiguration() {
    // Both delivery paths use the same empty inner payload, with independent cursors.
    // Add configuration encoding here when extending the schema and native decoders.
    return ByteBuffer.allocate(0);
  }

  static Set<ExecUnitType> supportedTypes(AgentMetadata metadata) {
    // Match the agent process architecture to artifacts actually built and packaged;
    // the OS architecture alone cannot prove that an artifact can run in the process.
    // Linux has only an x64 library; the bundled Windows converter defaults to
    // dual x86/x64 shellcode and the managed builds target AnyCPU.
    // ARM and unknown architectures have no artifact.
    if (metadata == null || metadata.os() == null) {
      return Set.of();
    }
    return switch (metadata.os()) {
      case WINDOWS -> metadata.processArch() == Architecture.X86
              || metadata.processArch() == Architecture.X64
          ? Set.of(ExecUnitType.SHELLCODE_NATIVE, ExecUnitType.DOTNET_DLL,
            ExecUnitType.DOTNET_EXE, ExecUnitType.NATIVE_LIB)
          : Set.of();
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
    // All default exec-units send UTF-8 "DONE", displayed in the output text result.
    // An empty final notification preserves that result; native terminal messages
    // determine command success/failure independently of the displayed text.
    if (!buffer.hasRemaining()) {
      return;
    }
    // Each sendResult payload must contain complete UTF-8 text. Developers can
    // replace DONE with their own output. Append to preserve previous results, and
    // decode before editing so malformed data cannot commit a partial update.
    final String text;
    try {
      text = StandardCharsets.UTF_8.newDecoder()
          .onMalformedInput(CodingErrorAction.REPORT)
          .onUnmappableCharacter(CodingErrorAction.REPORT)
          .decode(buffer.asReadOnlyBuffer()).toString();
    } catch (CharacterCodingException error) {
      throw new SerializationException("Command output must be valid UTF-8.", error);
    }
    editor.appendTextResult("output", text);
    editor.commit();
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
    // No state is owned by the default command. Handle status changes here if added.
    // The host reports lifecycle transitions through status. Track them only when
    // this invocation needs them, releasing server-side state on terminal transitions
    // and tolerating repeated notifications. This hook does not send the native
    // command's terminal IPC message. A command with no owned state can leave it empty.
  }

  @Override
  public void forceStop() throws ExecutionException {
    // No resources are owned by the default command. Release new resources here.
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
