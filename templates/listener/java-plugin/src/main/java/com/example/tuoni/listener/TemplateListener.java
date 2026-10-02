package com.example.tuoni.listener;

import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.PluginIpcType;
import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnit;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ExecutionException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.listener.Listener;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerContext;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerStatus;
import com.shelldot.tuoni.plugin.sdk.listener.ExecUnitListener;
import com.shelldot.tuoni.plugin.sdk.listener.ShellcodeListener;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadType;
import java.nio.ByteBuffer;
import java.util.Set;

public class TemplateListener implements ExecUnitListener, ShellcodeListener {

  private static final String SHELLCODE_RESOURCE = "/listener.shellcode";
  private static final String LINUX_RESOURCE = "/listener-linux.native64_so";
  private static final PayloadType LINUX_X64 =
      PayloadType.of(OperatingSystem.LINUX, Architecture.X64);
  private volatile ListenerStatus status = ListenerStatus.CREATED;

  public TemplateListener(
      long listenerId, Configuration configuration, ListenerContext listenerContext) {
    // TODO: Retain the validated configuration and context needed by this listener.
    // Store the stable listener identity, parsed settings, and ListenerContext
    // used to read metadata, resolve/register agents, and report activity. Declare
    // ownership of sessions, transport resources, and workers so partial startup
    // can be unwound. Keep construction free of network binding and background
    // work; those resources must be acquired and published by start().
  }

  @Override
  public String getInfo() {
    // Replace the placeholder with a concise snapshot of this listener's actual
    // endpoint and useful state. Read worker-updated values consistently and avoid
    // exposing credentials. Java startup reports local resource readiness; remote
    // health or telemetry needs received observations and their freshness rather
    // than being inferred from STARTED alone.
    return "TODO: Describe your listener.";
  }

  @Override
  public ListenerStatus getStatus() {
    return status;
  }

  @Override
  public void start() throws ExecutionException {
    // TODO: Initialize listener resources; set STARTED only after successful startup.
    // Bind/open the configured Java application transport and install its receive
    // and command-send handling. Keep session and worker references owned before
    // they can fail, unwind all partial acquisition on error, and retain the cause
    // in ExecutionException. Coordinate repeated starts and starts after delete
    // with the lifecycle policy; publish STARTED only once resources are usable.
    throw new ExecutionException("TODO: Implement listener startup.");
  }

  @Override
  public void stop() throws ExecutionException {
    // TODO: Release any resources acquired during startup.
    // Stop accepting sessions, signal cancellation, and unblock pending accepts,
    // reads, writes, and command waits. Cancel subscriptions, settle pending command
    // send statuses, await owned workers, then release sessions and transport state
    // before publishing STOPPED. Cleanup must also handle a failed partial start
    // and repeated calls; avoid waiting under locks that workers need to exit.
    status = ListenerStatus.STOPPED;
  }

  @Override
  public void delete() throws ExecutionException {
    stop();
    // TODO: Release any remaining listener-owned resources.
    // After shutdown, release persistent per-listener state that stop() intentionally
    // keeps for restart, including registrations or owned storage when applicable.
    // Make deletion safe to repeat and publish DELETED only after cleanup succeeds.
    // Define how later start/reconfigure requests reject a deleted listener without
    // recreating resources or leaving stale session references.
    status = ListenerStatus.DELETED;
  }

  @Override
  public Listener reconfigure(Configuration newConfiguration)
      throws ExecutionException, SerializationException, ValidationException {
    // Validate a complete candidate before changing active settings. Apply Java
    // resource changes in coordination with start/stop, and return this instance
    // or a replacement that preserves listenerId and ListenerContext according to
    // the chosen lifecycle design. Publish the candidate after successful startup;
    // preserve/restore the prior working state if replacement fails. Encoding a
    // native update is separate from proving it was delivered and applied. If
    // reconfiguration is unsupported, report that explicitly without changing state.
    TemplateListenerPlugin.validateConfiguration(newConfiguration);
    throw new ExecutionException("TODO: Implement listener reconfiguration.");
  }

  @Override
  public Set<PayloadType> getSupportedPayloadTypes() {
    // Advertise only OS/architecture combinations with matching packaged native
    // resources and implemented configuration/transport behavior. These scaffold
    // declarations describe intended targets; adding a target also requires its
    // build, artifact selection, entrypoint, and native protocol implementation.
    return Set.of(
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64),
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X86),
        LINUX_X64);
  }

  @Override
  public Set<ExecUnitType> getSupportedExecUnitTypes(PayloadType payloadType) {
    // Map each supported payload target to artifact formats its loader can execute.
    // Keep this result consistent with generateExecUnit() resource and entrypoint
    // selection; unsupported combinations must return an empty set. Linux uses the
    // run export of its native library, while Windows uses patched shellcode here.
    if (LINUX_X64.equals(payloadType)) {
      return Set.of(ExecUnitType.NATIVE_LIB);
    }
    return getSupportedPayloadTypes().contains(payloadType)
        ? Set.of(ExecUnitType.SHELLCODE_NATIVE) : Set.of();
  }

  @Override
  public ExecUnit generateExecUnit(ExecUnitType type, String pipeName, PayloadType payloadType)
      throws SerializationException {
    // Select the artifact for this complete type/OS/architecture combination and
    // pair it with configuration encoded from the validated active settings. Replace
    // the empty configuration below with the same inner bytes consumed by native
    // Connect()/connect(); the SDK/agent adds the host IPC envelope. Preserve the
    // Windows pipe-name patch and Linux run entrypoint. Return each configuration
    // buffer at position zero with its limit equal to the encoded payload length,
    // and report missing resources or encoding failures as SerializationException.
    if (!getSupportedExecUnitTypes(payloadType).contains(type)) {
      throw new SerializationException(
          "Unsupported execution unit type " + type + " for payload type " + payloadType);
    }
    boolean linux = LINUX_X64.equals(payloadType);
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
  public ShellCodeWithConf generateShellCode(String pipeName, PayloadType payloadType)
      throws SerializationException {
    // Produce the supported Windows shellcode with its UTF-16LE pipe placeholder
    // patched, plus the same native configuration bytes used by generateExecUnit().
    // Replace the empty buffer with a shared encoder for active validated settings,
    // preserving exact buffer position/limit and matching the native decoder. Do
    // not prepend pipe/TLV framing here; the SDK/agent owns that outer envelope.
    if (!getSupportedExecUnitTypes(payloadType).contains(ExecUnitType.SHELLCODE_NATIVE)) {
      throw new SerializationException("Unsupported shellcode payload type: " + payloadType);
    }
    return new ShellCodeWithConf(
        ShellcodeResource.load(getClass(), SHELLCODE_RESOURCE, pipeName),
        ByteBuffer.allocate(0),
        PluginIpcType.NAMED_PIPE);
  }

  @Override
  public ByteBuffer serializeUpdatedConfiguration(Configuration configuration)
      throws SerializationException {
    // Encode the supplied candidate using the native configuration contract shared
    // by startup generation and every in-scope decoder. This hook serializes bytes
    // without mutating active Java settings or itself delivering an update. Return
    // an exact payload buffer at position zero; wrap candidate validation failures
    // in SerializationException because this SDK signature cannot throw them.
    // If native updates are unsupported, replace the TODO with an explanatory
    // SerializationException rather than returning an empty success payload.
    throw new SerializationException("TODO: Implement listener configuration serialization.");
  }
}
