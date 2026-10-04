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
  private final long listenerId;
  private final ListenerContext listenerContext;
  private volatile ListenerStatus status = ListenerStatus.CREATED;

  public TemplateListener(
      long listenerId, Configuration configuration, ListenerContext listenerContext) {
    this.listenerId = listenerId;
    this.listenerContext = listenerContext;
    // No configuration fields or transport resources are owned by the default.
  }

  @Override
  public String getInfo() {
    // Local lifecycle state only; the default has no endpoint or remote telemetry.
    return "Listener template " + listenerId + ": " + status;
  }

  @Override
  public ListenerStatus getStatus() {
    return status;
  }

  @Override
  public synchronized void start() throws ExecutionException {
    requireNotDeleted();
    if (status == ListenerStatus.STARTED) {
      return;
    }
    // TODO: Open the data traffic channel, receive/register agents through
    // listenerContext, and send their queued commands. Own and unwind resources
    // before publishing STARTED when that channel is implemented.
    status = ListenerStatus.STARTED;
  }

  @Override
  public synchronized void stop() throws ExecutionException {
    // TODO: Close the data traffic channel and unblock/join its workers once added.
    // The idle default owns no sockets, sessions, subscriptions, or workers.
    if (status != ListenerStatus.DELETED) {
      status = ListenerStatus.STOPPED;
    }
  }

  @Override
  public synchronized void delete() throws ExecutionException {
    stop();
    // TODO: Release persistent data-channel state if it is introduced.
    status = ListenerStatus.DELETED;
  }

  @Override
  public synchronized Listener reconfigure(Configuration newConfiguration)
      throws ExecutionException, SerializationException, ValidationException {
    requireNotDeleted();
    TemplateListenerPlugin.validateConfiguration(newConfiguration);
    // With no fields, a valid replacement changes nothing and preserves status.
    // TODO: Apply data-channel settings atomically, retaining the previous working
    // resources if an update fails, when configuration fields are introduced.
    return this;
  }

  private void requireNotDeleted() throws ExecutionException {
    if (status == ListenerStatus.DELETED) {
      throw new ExecutionException("The listener has been deleted.");
    }
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
    if (payloadType == null) {
      return Set.of();
    }
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
    // pair it with configuration encoded from the validated active settings. Extend
    // the shared encoder with the same inner bytes consumed by native
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
        .configuration(serializeConfiguration())
        .entrypoint(linux ? "run" : null)
        .build();
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, PayloadType payloadType)
      throws SerializationException {
    // Produce the supported Windows shellcode with its UTF-16LE pipe placeholder
    // patched, plus the same native configuration bytes used by generateExecUnit().
    // Extend the shared encoder for active validated settings,
    // preserving exact buffer position/limit and matching the native decoder. Do
    // not prepend pipe/TLV framing here; the SDK/agent owns that outer envelope.
    if (!getSupportedExecUnitTypes(payloadType).contains(ExecUnitType.SHELLCODE_NATIVE)) {
      throw new SerializationException("Unsupported shellcode payload type: " + payloadType);
    }
    return new ShellCodeWithConf(
        ShellcodeResource.load(getClass(), SHELLCODE_RESOURCE, pipeName),
        serializeConfiguration(),
        PluginIpcType.NAMED_PIPE);
  }

  @Override
  public ByteBuffer serializeUpdatedConfiguration(Configuration configuration)
      throws SerializationException {
    try {
      TemplateListenerPlugin.validateConfiguration(configuration);
    } catch (ValidationException error) {
      throw new SerializationException("Invalid listener configuration.", error);
    }
    // A valid {} replacement has no native fields to change. Serialization does
    // not establish delivery; add delivery/application when fields are introduced.
    return serializeConfiguration();
  }

  private ByteBuffer serializeConfiguration() {
    // Fresh readable buffer shared by startup and no-field replacement encoding.
    return ByteBuffer.allocate(0);
  }
}
