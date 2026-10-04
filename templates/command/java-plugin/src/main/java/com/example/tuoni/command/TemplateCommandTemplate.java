package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.command.Command;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandTemplate;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.common.AgentType;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.configuration.JsonConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.MultipartConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.NamedConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import java.util.List;
import java.util.Set;

public class TemplateCommandTemplate implements CommandTemplate {

  static final String NAME = "template-command";

  @Override
  public Set<ExecUnitType> getSupportedExecUnitTypes() {
    // Advertise the union of execution formats supplied by this command template.
    // Per-agent checks below and on TemplateCommand must narrow it to resources
    // that match the agent's OS and process architecture before code is generated.
    return Set.of(ExecUnitType.SHELLCODE_NATIVE, ExecUnitType.NATIVE_LIB);
  }

  @Override
  public String getName() {
    // This name identifies the command for registration, configuration examples and
    // unsupported-update errors. Choose a stable name when creating a real command.
    return NAME;
  }

  @Override
  public String getDescription() {
    return "Returns DONE and completes successfully without performing any operation.";
  }

  @Override
  public List<NamedConfiguration> getExampleConfigurations() {
    JsonConfiguration empty = () -> "{}";
    return List.of(new NamedConfiguration("default", empty));
  }

  @Override
  public ConfigurationSchema getConfigurationSchema() {
    // Supply the operator-facing JSON and upload field definitions. Keep this schema
    // consistent with Java validation and the values encoded for both native targets.
    return new TemplateConfigurationSchema();
  }

  @Override
  public boolean canSendToAgent(AgentInfo agentInfo) {
    // Decide whether this command can be offered to this agent before an invocation
    // is created. Check agent type, metadata, OS and process architecture against the
    // built artifacts; a supported OS alone does not establish architecture support.
    // Keep direct generation calls equally guarded, including unknown metadata.
    return agentInfo != null && agentInfo.getType() == AgentType.SHELLCODE_AGENT
        && !TemplateCommand.supportedTypes(agentInfo.getLatestMetadata()).isEmpty();
  }

  @Override
  public void validateConfiguration(Configuration configuration, AgentInfo agentInfo)
      throws ValidationException {
    JsonConfiguration json;
    if (configuration instanceof JsonConfiguration value) {
      json = value;
    } else if (configuration instanceof MultipartConfiguration multipart) {
      if (!multipart.files().isEmpty()) {
        throw new ValidationException("The template command does not accept file uploads.");
      }
      json = multipart.jsonConfiguration();
    } else {
      throw new ValidationException("Expected an empty JSON object: {}.");
    }
    String text = json == null ? null : json.toJSON();
    // This is the complete grammar for our empty-object schema. Add a JSON parser
    // and typed configuration when adding fields; no parser dependency is needed yet.
    if (text == null || !text.matches("[ \\t\\r\\n]*\\{[ \\t\\r\\n]*\\}[ \\t\\r\\n]*")) {
      throw new ValidationException("The template command accepts only an empty JSON object: {}.");
    }
  }

  @Override
  public Command createCommand(
      int commandId,
      AgentInfo agentInfo,
      Configuration configuration,
      CommandContext commandContext)
      throws ValidationException, InitializationException {
    // Create a separate command instance for each commandId after validating input.
    // As configuration grows, parse once here and pass the typed value to the command
    // instead of reparsing raw input differently in each generation path. Preserve
    // per-invocation ownership, and use InitializationException for setup failures
    // that occur after otherwise valid configuration has been accepted.
    validateConfiguration(configuration, agentInfo);
    return new TemplateCommand(commandId, agentInfo, configuration, commandContext);
  }
}
