package com.shelldot.tuoni.examples.plugin.dotnetpayload;

public record DotnetPayloadPluginConfiguration() {
  public static final String JSON_SCHEMA =
      """
      {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
          "type": {
            "type": "string",
            "enum": [
              "EXECUTABLE"
            ]
          }
        },
        "required": [
          "type"
        ]
      }
      """;

}
