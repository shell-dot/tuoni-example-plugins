package com.shelldot.tuoni.examples.plugin.dotnetpayload.utils;

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

}
