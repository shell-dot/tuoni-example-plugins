package com.shelldot.tuoni.examples.plugin.echo.utils;

import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

public class ShellcodeUtil {

  public static ByteBuffer readClasspathResourceToBuffer(Class<?> clazz, String path)
      throws SerializationException {
    if (path == null) {
      throw new SerializationException("failed to find classpath resource 'null'");
    }
    if (clazz == null) {
      throw new SerializationException(
          "failed to find classpath resource '%s' from null class".formatted(path));
    }

    try (InputStream inputStream = clazz.getResourceAsStream(path)) {
      if (inputStream != null) {
        return ByteBuffer.wrap(inputStream.readAllBytes()).order(ByteOrder.LITTLE_ENDIAN);
      }
    } catch (IOException e) {
      throw new SerializationException("failed to find classpath resource '%s'".formatted(path), e);
    }

    ClassLoader classLoader = clazz.getClassLoader();
    if (classLoader == null) {
      throw new SerializationException(
          "failed to find classpath resource '%s' from null classloader".formatted(path));
    }
    try (InputStream inputStream = classLoader.getResourceAsStream(path)) {
      if (inputStream == null) {
        throw new SerializationException("failed to find classpath resource '%s'".formatted(path));
      }
      return ByteBuffer.wrap(inputStream.readAllBytes()).order(ByteOrder.LITTLE_ENDIAN);
    } catch (IOException e) {
      throw new SerializationException("failed to read classpath resource '%s'".formatted(path), e);
    }
  }

  public static void replaceBytesInBuffer(ByteBuffer buffer, byte[] oldBytes, byte[] newBytes)
      throws SerializationException {
    int idx = ShellcodeUtil.indexOf(buffer.array(), oldBytes);
    if (idx == -1) {
      throw new SerializationException(
          "failed to replace bytes in buffer due to not finding original bytes in the shellcode");
    }
    if (oldBytes.length != newBytes.length) {
      throw new SerializationException(
          "failed to replace bytes in buffer due to different length arrays (old=%d, new=%d)"
              .formatted(oldBytes.length, newBytes.length));
    }
    buffer.put(idx, newBytes, 0, newBytes.length);
  }

  private static int indexOf(byte[] outerArray, byte[] subArray) {
    if (outerArray == null || subArray == null || subArray.length == 0) {
      return -1;
    }
    if (subArray.length > outerArray.length) {
      return -1;
    }

    for (int i = 0; i < outerArray.length - subArray.length + 1; ++i) {
      // Find the start of the searched array
      if (outerArray[i] == subArray[0]) {
        boolean found = true;
        // Check if following elements match the searched array
        for (int j = 1; j < subArray.length; ++j) {
          if (outerArray[i + j] != subArray[j]) {
            found = false;
            break;
          }
        }
        if (found) {
          return i;
        }
      }
    }
    return -1;
  }
}
