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
    return Set.of(ExecUnitType.SHELLCODE_NATIVE, ExecUnitType.NATIVE_LIB);
  }

  @Override
  public String getName() {
    return NAME;
  }

  @Override
  public String getDescription() {
    return "TODO: Describe your command.";
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
  public boolean canSendToAgent(AgentInfo agentInfo) {
    return agentInfo.getType() == AgentType.SHELLCODE_AGENT
        && (agentInfo.getLatestMetadata().os() == OperatingSystem.WINDOWS
            || (agentInfo.getLatestMetadata().os() == OperatingSystem.LINUX
                && agentInfo.getLatestMetadata().processArch() == Architecture.X64));
  }

  @Override
  public void validateConfiguration(Configuration configuration, AgentInfo agentInfo)
      throws ValidationException {
    // TODO: Parse and validate the configuration against your schema.
    throw new ValidationException("TODO: Implement command configuration validation.");
  }

  @Override
  public Command createCommand(
      int commandId,
      AgentInfo agentInfo,
      Configuration configuration,
      CommandContext commandContext)
      throws ValidationException, InitializationException {
    validateConfiguration(configuration, agentInfo);
    return new TemplateCommand(commandId, agentInfo, configuration, commandContext);
  }
}
