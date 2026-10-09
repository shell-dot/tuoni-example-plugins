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
  // This operating system/architecture pair is the template's advertised output and is used when
  // selecting compatible listener code. Align it with the actual payload program and any embedded
  // native code; register additional templates if the plugin builds for other target platforms.
  static final PayloadType TYPE = PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64);

  @Override
  public String getName() {
    // Choose a stable, descriptive template name that distinguishes this build target from other
    // templates. Tuoni uses it when saving payloads, so treat renaming a distributed template as a
    // compatibility decision rather than changing this value for each generated file.
    return "template-payload";
  }

  @Override
  public String getDescription() {
    // Describe what this template builds, its supported output formats and runtime requirements,
    // and any listener limitations so users can choose suitable payload generation options.
    return "TODO: Describe your payload.";
  }

  @Override
  public List<NamedConfiguration> getExampleConfigurations() {
    // TODO: Add sample configurations once the schema is defined.
    // Return named presets containing the same Configuration representation that validation and
    // creation accept. Include valid minimal and common build options, with values matching the
    // advertised schema. Keep examples current when fields or defaults change; an empty list is
    // appropriate only when the template does not provide presets.
    return List.of();
  }

  @Override
  public ConfigurationSchema getConfigurationSchema() {
    // Expose the schema for this template's user-supplied JSON options and uploaded files. Keep
    // it consistent with validation, example configurations, and the inputs consumed by the
    // builder so the server and clients can describe and check the same build contract.
    return new TemplateConfigurationSchema();
  }

  @Override
  public PayloadType getPayloadType() {
    // Advertise the target operating system and architecture before listener code is requested.
    // The Payload returned by createPayload() must report this same target for its final bytes.
    return TYPE;
  }

  @Override
  public void validateConfiguration(Configuration configuration) throws ValidationException {
    // TODO: Parse and validate the configuration against your schema.
    // Accept the intended Configuration form (JSON, multipart, or binary), handle absent input
    // explicitly, and check required values, ranges, field combinations, and any uploaded file
    // requirements. Apply the same parsing/default rules that createPayload() uses. Return
    // normally for valid input; report actionable field or format errors as ValidationException.
    // This hook checks build inputs and must not generate the artifact or start its runtime.
    throw new ValidationException("TODO: Implement payload configuration validation.");
  }

  @Override
  public Payload createPayload(
      long payloadId, Configuration configuration, List<ListenerCode> listenerShellCodes)
      throws SerializationException, ValidationException {
    validateConfiguration(configuration);
    // TODO: Pass any required, validated creation inputs to your payload object.
    // This factory receives the server-assigned payloadId, the saved build configuration, and
    // listener code already generated for the selected listeners. Parse the configuration into
    // build options, enforce the listener count and representations that your runtime supports,
    // and capture those inputs plus required binary resources in a new Payload instance. Despite
    // the parameter name, ListenerCode may represent shellcode or an execunit; this template's
    // inherited default requests shellcode, and execunit support needs the corresponding template
    // capability override and runtime handling. Preserve listener configuration when embedding
    // its code, and carry payloadId into the artifact if the runtime format requires it. Report
    // invalid inputs as ValidationException and generation failures as SerializationException;
    // the returned object's serialize() produces the final file bytes.
    return new TemplatePayload();
  }
}
