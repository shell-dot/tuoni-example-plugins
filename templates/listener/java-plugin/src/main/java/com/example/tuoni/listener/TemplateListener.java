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
  }

  @Override
  public String getInfo() {
    return "TODO: Describe your listener.";
  }

  @Override
  public ListenerStatus getStatus() {
    return status;
  }

  @Override
  public void start() throws ExecutionException {
    // TODO: Initialize listener resources; set STARTED only after successful startup.
    throw new ExecutionException("TODO: Implement listener startup.");
  }

  @Override
  public void stop() throws ExecutionException {
    // TODO: Release any resources acquired during startup.
    status = ListenerStatus.STOPPED;
  }

  @Override
  public void delete() throws ExecutionException {
    stop();
    // TODO: Release any remaining listener-owned resources.
    status = ListenerStatus.DELETED;
  }

  @Override
  public Listener reconfigure(Configuration newConfiguration)
      throws ExecutionException, SerializationException, ValidationException {
    TemplateListenerPlugin.validateConfiguration(newConfiguration);
    throw new ExecutionException("TODO: Implement listener reconfiguration.");
  }

  @Override
  public Set<PayloadType> getSupportedPayloadTypes() {
    return Set.of(
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64),
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X86),
        LINUX_X64);
  }

  @Override
  public Set<ExecUnitType> getSupportedExecUnitTypes(PayloadType payloadType) {
    if (LINUX_X64.equals(payloadType)) {
      return Set.of(ExecUnitType.NATIVE_LIB);
    }
    return getSupportedPayloadTypes().contains(payloadType)
        ? Set.of(ExecUnitType.SHELLCODE_NATIVE) : Set.of();
  }

  @Override
  public ExecUnit generateExecUnit(ExecUnitType type, String pipeName, PayloadType payloadType)
      throws SerializationException {
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
    throw new SerializationException("TODO: Implement listener configuration serialization.");
  }
}
