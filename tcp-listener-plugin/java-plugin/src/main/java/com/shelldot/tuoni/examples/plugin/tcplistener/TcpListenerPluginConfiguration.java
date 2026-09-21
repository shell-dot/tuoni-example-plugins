package com.shelldot.tuoni.examples.plugin.tcplistener;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.JsonConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.MultipartConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;

public record TcpListenerPluginConfiguration(String connectBackAddress, int port) {

  public static final String JSON_SCHEMA =
      """
      {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
          "connectBackAddress": {
            "type": "string"
          },
          "port": {
            "type": "integer",
            "minimum": 1,
            "maximum": 65535
          }
        },
        "required": [
          "port",
          "connectBackAddress"
        ]
      }
      """;

  private static final ObjectMapper MAPPER = new ObjectMapper();

  public static TcpListenerPluginConfiguration fromConfiguration(Configuration configuration)
      throws ValidationException {
    try {
      JsonConfiguration json =
          switch (configuration) {
            case JsonConfiguration j -> j;
            case MultipartConfiguration m -> m.jsonConfiguration();
            default -> throw new ValidationException(
                "Unsupported configuration type: " + configuration.getClass().getSimpleName());
          };
      TcpListenerPluginConfiguration cfg =
          MAPPER.readValue(json.toJSON(), TcpListenerPluginConfiguration.class);
      if (cfg.port() < 1 || cfg.port() > 65535) {
        throw new ValidationException("port must be between 1 and 65535");
      }
      return cfg;
    } catch (ValidationException e) {
      throw e;
    } catch (Exception e) {
      throw new ValidationException("Invalid TCP listener configuration: " + e.getMessage());
    }
  }

  public ByteBuffer serializeForShellcode() {
    String fullConf = connectBackAddress + ":" + port;
    return ByteBuffer.wrap(fullConf.getBytes(StandardCharsets.UTF_8));
  }
}
