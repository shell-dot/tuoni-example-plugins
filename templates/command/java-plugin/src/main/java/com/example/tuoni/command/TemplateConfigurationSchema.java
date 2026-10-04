package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import java.util.List;

/**
 * The default no-op command accepts an empty JSON object and no file uploads.
 *
 * This schema describes operator input, not the native pipe envelope. Keep its field
 * types, required values, defaults and limits aligned with validateConfiguration and
 * the typed value serialized by both command generation paths. The scaffold currently
 * describes an empty object with no uploads; add only fields needed by the command.
 */
public record TemplateConfigurationSchema() implements ConfigurationSchema {

  @Override
  public String jsonSchema() {
    // Define JSON properties, human-readable descriptions, required fields and
    // constraints understood by the UI. Runtime validation must enforce the same
    // rules, including defaults and cross-field checks not expressible in the schema.
    // Keep additionalProperties behavior deliberate when adding or renaming fields.
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
    // Declare named multipart uploads separately from JSON properties when the
    // command needs file content. Each FileSchema supplies name, description and
    // required status; validation must also enforce counts, sizes and accepted content.
    // Deliver actual owned file bytes through the agreed payload, not only a filename.
    return List.of();
  }
}

