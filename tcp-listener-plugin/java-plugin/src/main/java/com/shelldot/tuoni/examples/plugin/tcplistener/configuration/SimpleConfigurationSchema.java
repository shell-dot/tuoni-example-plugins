package com.shelldot.tuoni.examples.plugin.tcplistener.configuration;

import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import java.util.List;

public record SimpleConfigurationSchema(String jsonSchema, List<FileSchema> fileSchemas)
    implements ConfigurationSchema {

  public SimpleConfigurationSchema(String jsonSchema) {
    this(jsonSchema, List.of());
  }
}
