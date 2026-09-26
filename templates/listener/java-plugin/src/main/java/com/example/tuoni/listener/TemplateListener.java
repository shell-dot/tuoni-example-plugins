package com.example.tuoni.listener;

import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.PluginIpcType;
import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ExecutionException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.listener.Listener;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerContext;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerStatus;
import com.shelldot.tuoni.plugin.sdk.listener.ShellcodeListener;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadType;
import java.nio.ByteBuffer;
import java.util.Set;

public class TemplateListener implements ShellcodeListener {

  private static final String SHELLCODE_RESOURCE = "/listener.shellcode";
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
        PayloadType.of(OperatingSystem.WINDOWS, Architecture.X86));
  }

  @Override
  public ShellCodeWithConf generateShellCode(String pipeName, PayloadType payloadType)
      throws SerializationException {
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
