package com.shelldot.tuoni.examples.plugin.echo;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

public record EchoConfigurationFile(Integer lines, byte[] echos) {
  public EchoConfigurationFile withFile(byte[] echos) {
    return new EchoConfigurationFile(this.lines, echos);
  }

  public static final String JSON_SCHEMA =
      """
      {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "tuoni-example-plugins/echo.schema.json",
        "title": "Echo command configuration",
        "type": "object",
        "properties": {
          "lines": {
            "description": "How many lines per second to echo",
            "type": "integer"
          }
        },
        "files": {
          "echos": {
            "type": "file",
            "description": "file to echo back",
            "required": true
          }
        },
        "required": ["message"]
      }
      """;

  public ByteBuffer serializeForShellcode() {
    ByteBuffer buffer = ByteBuffer.allocate(4 + (echos != null ? echos.length : 0));
    buffer.order(ByteOrder.LITTLE_ENDIAN);
    buffer.putInt(lines != null ? lines : 1);
    if (echos != null) {
      buffer.put(echos);
    }
    buffer.flip();
    return buffer;
  }
}
