package com.example.tuoni.payload;

import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import java.util.List;

/**
 * TODO: Describe your configuration fields and required values here.
 *
 * <p>This schema describes the user-supplied build options accepted by the payload template. Keep
 * JSON property names, required fields, defaults, and any uploaded-file names aligned with the
 * parser used by TemplatePayloadTemplate.validateConfiguration() and createPayload(). The empty
 * record is a schema provider; add a separate typed configuration model if the builder needs one.
 */
public record TemplateConfigurationSchema() implements ConfigurationSchema {

  @Override
  public String jsonSchema() {
    // Describe the JSON object accepted when saving or creating this payload: add properties,
    // types, required entries, value ranges, and useful descriptions for each build option. The
    // current schema accepts only an empty object. Schema defaults document intended values;
    // ensure the configuration parser applies any defaults that payload generation relies on.
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
    // Declare uploaded configuration files, such as an optional custom payload binary, by their
    // multipart field names, descriptions, and required flags. Those names must match the file
    // lookup in your configuration parser. Keep this empty if generation needs only JSON options;
    // validate file contents and compatibility in the template rather than relying on this list.
    return List.of();
  }
}

