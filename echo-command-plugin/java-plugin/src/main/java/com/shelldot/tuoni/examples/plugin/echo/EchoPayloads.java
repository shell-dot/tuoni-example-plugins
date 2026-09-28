package com.shelldot.tuoni.examples.plugin.echo;

import com.shelldot.tuoni.examples.plugin.echo.utils.ShellcodeUtil;
import com.shelldot.tuoni.plugin.sdk.common.AgentMetadata;
import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.PluginIpcType;
import com.shelldot.tuoni.plugin.sdk.common.ShellCodeWithConf;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;

final class EchoPayloads {
  private static final String DEFAULT_PIPE_NAME = "QQQWWWEEE";

  private EchoPayloads() {}

  static ShellCodeWithConf generate(
      Class<?> resourceOwner,
      String commandName,
      String pipeName,
      AgentMetadata metadata,
      ByteBuffer configuration)
      throws SerializationException {
    OperatingSystem os = metadata.os();
    if (os == OperatingSystem.LINUX && metadata.processArch() != Architecture.X64) {
      throw new SerializationException("Linux echo execunits require an x64 agent process");
    }
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
    return new ShellCodeWithConf(payload, configuration, PluginIpcType.NAMED_PIPE);
  }
}
