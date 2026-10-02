package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.command.Command;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandTemplate;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.common.AgentType;
import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
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
    // TODO: Explain the operator-visible action, important inputs and resulting
    // output. This description is command discovery/help text; describe the actual
    // implemented behavior and any meaningful platform limitations.
    return "TODO: Describe your command.";
  }

  @Override
  public List<NamedConfiguration> getExampleConfigurations() {
    // TODO: Add sample configurations once the schema is defined.
    // Return named SDK configurations that pass this template's actual validator,
    // illustrating a minimal request and useful optional fields without secrets.
    // Keep examples in step with schema/default changes; use an empty-object example
    // if the implemented command intentionally accepts no configuration fields.
    return List.of();
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
    return agentInfo.getType() == AgentType.SHELLCODE_AGENT
        && (agentInfo.getLatestMetadata().os() == OperatingSystem.WINDOWS
            || (agentInfo.getLatestMetadata().os() == OperatingSystem.LINUX
                && agentInfo.getLatestMetadata().processArch() == Architecture.X64));
  }

  @Override
  public void validateConfiguration(Configuration configuration, AgentInfo agentInfo)
      throws ValidationException {
    // TODO: Parse and validate the configuration against your schema.
    // Accept only supported SDK configuration types, parse JSON/files into one typed
    // value, apply documented defaults and check required fields, types, bounds and
    // cross-field rules. For multipart input, resolve uploaded bytes and metadata
    // before validation that uses them, and bound reads/counts explicitly.
    // Use the same parser during createCommand so acceptance and serialization agree;
    // no runtime operation or pipe connection should start during validation.
    // Report invalid fields as ValidationException with useful field information.
    // A command without user fields still needs to accept its valid empty object.
    throw new ValidationException("TODO: Implement command configuration validation.");
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
