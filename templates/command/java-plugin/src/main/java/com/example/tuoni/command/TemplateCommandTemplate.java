package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.command.Command;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandTemplate;
import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.common.AgentType;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.configuration.NamedConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import java.util.List;

public class TemplateCommandTemplate implements CommandTemplate {

  static final String NAME = "template-command";

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
        && agentInfo.getLatestMetadata().os() == OperatingSystem.WINDOWS;
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
