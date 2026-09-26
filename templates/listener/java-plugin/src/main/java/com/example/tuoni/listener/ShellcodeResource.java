package com.example.tuoni.listener;

import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

/** Loads a packaged execunit and replaces its fixed pipe-name placeholder. */
final class ShellcodeResource {

  private static final byte[] PIPE_PLACEHOLDER =
      "QQQWWWEEE".getBytes(StandardCharsets.UTF_16LE);

  private ShellcodeResource() {}

  static ByteBuffer load(Class<?> owner, String resourcePath, String pipeName)
      throws SerializationException {
    if (pipeName == null) {
      throw new SerializationException("Pipe name is missing");
    }
    byte[] pipeBytes = pipeName.getBytes(StandardCharsets.UTF_16LE);
    if (pipeBytes.length != PIPE_PLACEHOLDER.length) {
      throw new SerializationException("Pipe name must match the placeholder length");
    }

    byte[] shellcode;
    try (InputStream resource = owner.getResourceAsStream(resourcePath)) {
      if (resource == null) {
        throw new SerializationException("Missing shellcode resource: " + resourcePath);
      }
      shellcode = resource.readAllBytes();
    } catch (IOException e) {
      throw new SerializationException("Failed to read shellcode resource: " + resourcePath, e);
    }

    boolean replaced = false;
    for (int offset = indexOf(shellcode, PIPE_PLACEHOLDER, 0);
        offset >= 0;
        offset = indexOf(shellcode, PIPE_PLACEHOLDER, offset + PIPE_PLACEHOLDER.length)) {
      System.arraycopy(pipeBytes, 0, shellcode, offset, pipeBytes.length);
      replaced = true;
    }
    if (!replaced) {
      throw new SerializationException("Pipe-name placeholder missing from " + resourcePath);
    }
    return ByteBuffer.wrap(shellcode).order(ByteOrder.LITTLE_ENDIAN);
  }

  private static int indexOf(byte[] bytes, byte[] sought, int start) {
    for (int i = start; i <= bytes.length - sought.length; i++) {
      int j = 0;
      while (j < sought.length && bytes[i + j] == sought[j]) {
        j++;
      }
      if (j == sought.length) {
        return i;
      }
    }
    return -1;
  }
}
