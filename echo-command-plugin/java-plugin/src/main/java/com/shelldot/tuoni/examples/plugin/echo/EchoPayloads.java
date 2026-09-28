package com.shelldot.tuoni.examples.plugin.echo;

import com.shelldot.tuoni.examples.plugin.echo.utils.ShellcodeUtil;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnit;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
import com.shelldot.tuoni.plugin.sdk.common.AgentMetadata;
import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.PluginIpcType;
import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.Set;

final class EchoPayloads {
  private static final String DEFAULT_PIPE_NAME = "QQQWWWEEE";

  private EchoPayloads() {}

  static Set<ExecUnitType> supportedTypes(AgentMetadata metadata) {
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

  static ExecUnit generate(
      Class<?> resourceOwner,
      String commandName,
      ExecUnitType type,
      String pipeName,
      AgentMetadata metadata,
      ByteBuffer configuration)
      throws SerializationException {
    if (!supportedTypes(metadata).contains(type)) {
      throw new SerializationException(
          "Unsupported execution unit type " + type + " for agent " + metadata);
    }
    OperatingSystem os = metadata.os();
    String path =
        switch (os) {
          case WINDOWS -> "/shellcode/" + commandName + ".shellcode";
          case LINUX -> "/shellcode/" + commandName + "-linux.native64_so";
          default -> throw new SerializationException("Unsupported agent OS: " + os);
        };
    ByteBuffer payload = ShellcodeUtil.readClasspathResourceToBuffer(resourceOwner, path);
    if (os == OperatingSystem.WINDOWS) {
      ShellcodeUtil.replaceBytesInBuffer(
          payload,
          DEFAULT_PIPE_NAME.getBytes(StandardCharsets.UTF_16LE),
          pipeName.getBytes(StandardCharsets.UTF_16LE));
    }
    return ExecUnit.builder()
        .code(payload)
        .type(type)
        .ipcType(PluginIpcType.NAMED_PIPE)
        .configuration(configuration)
        .entrypoint(os == OperatingSystem.LINUX ? "run" : null)
        .build();
  }

  static ShellCodeWithConf generateShellCode(
      Class<?> resourceOwner,
      String commandName,
      String pipeName,
      AgentMetadata metadata,
      ByteBuffer configuration)
      throws SerializationException {
    ExecUnit execUnit =
        generate(
            resourceOwner,
            commandName,
            ExecUnitType.SHELLCODE_NATIVE,
            pipeName,
            metadata,
            configuration);
    return new ShellCodeWithConf(execUnit.code(), execUnit.configuration(), execUnit.ipcType());
  }
}
