package com.example.tuoni.payload;

import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.configuration.NamedConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.payload.ListenerCode;
import com.shelldot.tuoni.plugin.sdk.payload.Payload;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadTemplate;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadType;
import java.util.List;

public class TemplatePayloadTemplate implements PayloadTemplate {

  // TODO: Choose the target platform for your payload.
  static final PayloadType TYPE = PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64);

  @Override
  public String getName() {
    return "template-payload";
  }

  @Override
  public String getDescription() {
    return "TODO: Describe your payload.";
  }

  @Override
  public List<NamedConfiguration> getExampleConfigurations() {
    // TODO: Add sample configurations once the schema is defined.
    return List.of();
  }

  @Override
  public ConfigurationSchema getConfigurationSchema() {
    return new TemplateConfigurationSchema();
  }

  @Override
  public PayloadType getPayloadType() {
    return TYPE;
  }

  @Override
  public void validateConfiguration(Configuration configuration) throws ValidationException {
    // TODO: Parse and validate the configuration against your schema.
    throw new ValidationException("TODO: Implement payload configuration validation.");
  }

  @Override
  public Payload createPayload(
      long payloadId, Configuration configuration, List<ListenerCode> listenerShellCodes)
      throws SerializationException, ValidationException {
    validateConfiguration(configuration);
    // TODO: Pass any required, validated creation inputs to your payload object.
    return new TemplatePayload();
  }
}
