package com.shelldot.tuoni.examples.plugin.echo;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.shelldot.tuoni.examples.plugin.echo.configuration.JacksonJsonConfiguration;
import com.shelldot.tuoni.examples.plugin.echo.configuration.SimpleConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.common.AgentType;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.command.Command;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandPluginContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandTemplate;
import com.shelldot.tuoni.plugin.sdk.common.AgentMetadata;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.configuration.JsonConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.NamedConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.common.validation.ValidationViolation;

import java.util.ArrayList;
import java.util.List;

public class EchoCommandOngoingMoreDataTemplate implements CommandTemplate {

  static final String NAME = "echo-ongoing-more-data";
  static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

  public EchoCommandOngoingMoreDataTemplate(CommandPluginContext pluginContext) {
  }

  @Override
  public String getName() {
    return NAME;
  }

  @Override
  public String getDescription() {
    return "Echoes the message sent to agent back to the server and accepts ongoing data via TCP port.";
  }

  @Override
  public List<NamedConfiguration> getExampleConfigurations() throws SerializationException {
    EchoConfigurationOngoingMoreData exampleEchoConf = new EchoConfigurationOngoingMoreData("First message", 1234);
    JacksonJsonConfiguration jsonConf =
        new JacksonJsonConfiguration(OBJECT_MAPPER.convertValue(exampleEchoConf, ObjectNode.class));

    return List.of(new NamedConfiguration("example-port-1234", jsonConf));
  }

  @Override
  public ConfigurationSchema getConfigurationSchema() throws SerializationException {
    return new SimpleConfigurationSchema(EchoConfigurationOngoingMoreData.JSON_SCHEMA);
  }

  @Override
  public boolean canSendToAgent(AgentInfo agentInfo) {
    return AgentType.SHELLCODE_AGENT == agentInfo.getType() && agentInfo.getLatestMetadata().os() == OperatingSystem.WINDOWS;
  }

  @Override
  public void validateConfiguration(AgentMetadata agentMetadata, Configuration configuration)
      throws ValidationException {
    EchoConfigurationOngoingMoreData echoConfiguration = parseConfiguration(configuration);
    validateEchoConfiguration(echoConfiguration);
  }

  @Override
  public Command createCommand(
      int commandId,
      AgentInfo agentInfo,
      Configuration configuration,
      CommandContext commandContext)
      throws ValidationException, InitializationException {
    EchoConfigurationOngoingMoreData echoConfiguration = parseConfiguration(configuration);
    validateEchoConfiguration(echoConfiguration);
    return new EchoCommandOngoingMoreData(commandId, agentInfo, echoConfiguration, commandContext);
  }

  private void validateEchoConfiguration(EchoConfigurationOngoingMoreData echoConfiguration)
      throws ValidationException {
    ArrayList<ValidationViolation> violations = new ArrayList<>();
    if (echoConfiguration.message() == null) {
      violations.add(
          new ValidationViolation(
              "message", "must not be null", ValidationViolation.ViolationType.ERROR));
    }
    if (echoConfiguration.port() == null) {
      violations.add(
          new ValidationViolation(
              "port", "must not be null", ValidationViolation.ViolationType.ERROR));
    }
    if (echoConfiguration.port() < 1 || echoConfiguration.port() > 65535) {
      violations.add(
          new ValidationViolation(
              "port",
              "must be between 1 and 65535",
              ValidationViolation.ViolationType.ERROR));
    }
    if (!violations.isEmpty()) {
      throw new ValidationException(
          "Invalid echo command configuration", violations);
    }
  }

  private EchoConfigurationOngoingMoreData parseConfiguration(Configuration configuration)
      throws ValidationException {
    if (!(configuration instanceof JsonConfiguration jsonConfiguration)) {
      throw new ValidationException(
          "Configuration must be a JSON object",
          List.of(
              new ValidationViolation(
                  "configuration",
                  "must be JSON object",
                  ValidationViolation.ViolationType.ERROR)));
    }

    try {
      return OBJECT_MAPPER.readValue(jsonConfiguration.toJSON(), EchoConfigurationOngoingMoreData.class);
    } catch (JsonProcessingException e) {
      String errorDescription =
          "error while parsing configuration JSON: %s".formatted(e.getMessage());
      throw new ValidationException(
          "Failed to parse configuration JSON",
          e,
          List.of(
              new ValidationViolation(
                  "configuration", errorDescription, ValidationViolation.ViolationType.ERROR)));
    }
  }
}
