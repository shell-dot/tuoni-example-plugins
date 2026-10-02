package com.shelldot.tuoni.examples.plugin.echo;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

public record EchoConfiguration(String message) {

  public static final String JSON_SCHEMA =
      """
      {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "tuoni-example-plugins/echo.schema.json",
        "title": "Echo command configuration",
        "type": "object",
        "properties": {
          "message": {
            "description": "Message to send to agent",
            "type": "string"
          }
        },
        "required": ["message"]
      }
      """;

  public ByteBuffer serializeForShellcode() {
    return StandardCharsets.UTF_8.encode(message).asReadOnlyBuffer().order(ByteOrder.LITTLE_ENDIAN);
  }
}
