package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import java.util.List;

/** TODO: Describe your configuration fields and required values here. */
public record TemplateConfigurationSchema() implements ConfigurationSchema {

  @Override
  public String jsonSchema() {
    return """
        {
          "$schema": "https://json-schema.org/draft/2020-12/schema",
          "type": "object",
          "properties": {},
          "additionalProperties": false
        }
        """;
  }

  @Override
  public List<FileSchema> fileSchemas() {
    return List.of();
  }
}

