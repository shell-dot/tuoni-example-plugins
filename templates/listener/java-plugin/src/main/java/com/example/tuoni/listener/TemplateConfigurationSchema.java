package com.example.tuoni.listener;

import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import java.util.List;

/**
 * The idle default accepts an empty JSON object and no uploads.
 * TODO: Add configuration fields when implementing the data traffic channel.
 * This is the public configuration contract used to render and validate listener
 * settings. Define Java-side transport settings and native connection settings
 * with their defaults, units, limits, and required relationships. Keep both schema
 * methods aligned with the parser in TemplateListenerPlugin; the empty object
 * below is a scaffold and does not define an implemented listener protocol.
 */
public record TemplateConfigurationSchema() implements ConfigurationSchema {

  @Override
  public String jsonSchema() {
    // Describe JSON scalar, object, and list fields using the declared schema
    // dialect, including required names, accepted values, and defaults. A field
    // default in the schema must also be applied by Java parsing. Keep resource
    // binding and live-update restrictions explicit in field descriptions where
    // they affect users; schema generation must work without plugin initialization.
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
    // Declare separately uploaded configuration files, such as a certificate or
    // key, only when the listener requires them. Their names must match attachment
    // lookups in validation, and their content must be checked before use. Keep an
    // empty list when there are no file inputs; do not put uploaded file bytes or
    // assume file paths in the JSON schema as a substitute for this SDK contract.
    return List.of();
  }
}

