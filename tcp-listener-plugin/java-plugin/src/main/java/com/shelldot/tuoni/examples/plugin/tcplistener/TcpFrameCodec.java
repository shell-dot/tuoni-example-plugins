package com.shelldot.tuoni.examples.plugin.tcplistener;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

final class TcpFrameCodec {

  static final int MAX_FRAME_BYTES = 64 * 1024 * 1024;

  private TcpFrameCodec() {}

  static int readLeInt(InputStream in) throws IOException {
    byte[] bytes = readFully(in, 4);
    return ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).getInt();
  }

  static void writeLeInt(OutputStream out, int value) throws IOException {
    ByteBuffer buffer = ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(value);
    out.write(buffer.array());
  }

  static byte[] readFully(InputStream in, int length) throws IOException {
    if (length < 0) {
      throw new IOException("Refusing to read negative byte count: " + length);
    }
    byte[] buffer = new byte[length];
    int offset = 0;
    while (offset < length) {
      int read = in.read(buffer, offset, length - offset);
      if (read < 0) {
        throw new IOException("Unexpected EOF after " + offset + " of " + length + " bytes");
      }
      offset += read;
    }
    return buffer;
  }
}
