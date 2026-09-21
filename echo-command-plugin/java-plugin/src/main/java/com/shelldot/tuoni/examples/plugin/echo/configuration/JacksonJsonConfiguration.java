package com.shelldot.tuoni.examples.plugin.echo.configuration;

import com.fasterxml.jackson.databind.node.ObjectNode;
import com.shelldot.tuoni.plugin.sdk.common.configuration.JsonConfiguration;

public record JacksonJsonConfiguration(ObjectNode objectNode) implements JsonConfiguration {

  @Override
  public String toJSON() {
    return objectNode.toPrettyString();
  }
}
