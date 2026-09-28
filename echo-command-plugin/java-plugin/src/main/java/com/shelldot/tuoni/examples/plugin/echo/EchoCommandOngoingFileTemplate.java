package com.shelldot.tuoni.examples.plugin.echo;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.json.JsonMapper;
import com.shelldot.tuoni.examples.plugin.echo.configuration.JacksonJsonConfiguration;
import com.shelldot.tuoni.examples.plugin.echo.configuration.SimpleConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.AgentInfo;
import com.shelldot.tuoni.plugin.sdk.common.AgentType;
import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.command.Command;
import com.shelldot.tuoni.plugin.sdk.command.CommandContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandTemplate;
import com.shelldot.tuoni.plugin.sdk.command.ExecUnitType;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.configuration.FilePart;
import com.shelldot.tuoni.plugin.sdk.common.configuration.MultipartConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.NamedConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.common.validation.ValidationViolation;
import java.util.List;
import java.util.Set;
import java.io.IOException;

public class EchoCommandOngoingFileTemplate implements CommandTemplate {

  static final String NAME = "echo-ongoing-file";
  static final JsonMapper OBJECT_MAPPER = JsonMapper.builderWithJackson2Defaults().build();

  @Override
  public String getName() {
    return NAME;
  }

  @Override
  public Set<ExecUnitType> getSupportedExecUnitTypes() {
    return Set.of(ExecUnitType.SHELLCODE_NATIVE, ExecUnitType.NATIVE_LIB);
  }

  @Override
  public String getDescription() {
    return "Echoes the lines in a file back to the server";
  }

  @Override
  public List<NamedConfiguration> getExampleConfigurations() throws SerializationException {
    JacksonJsonConfiguration jsonConf =
        new JacksonJsonConfiguration(OBJECT_MAPPER.createObjectNode().put("lines", 1));

    return List.of(new NamedConfiguration("line-by-line", jsonConf));
  }

  @Override
  public ConfigurationSchema getConfigurationSchema() throws SerializationException {
    return new SimpleConfigurationSchema(
        EchoConfigurationFile.JSON_SCHEMA,
        List.of(new ConfigurationSchema.FileSchema("echos", "File to echo back", true)));
  }

  @Override
  public boolean canSendToAgent(AgentInfo agentInfo) {
    return AgentType.SHELLCODE_AGENT == agentInfo.getType()
        && (agentInfo.getLatestMetadata().os() == OperatingSystem.WINDOWS
            || (agentInfo.getLatestMetadata().os() == OperatingSystem.LINUX
                && agentInfo.getLatestMetadata().processArch() == Architecture.X64));
  }

  @Override
  public void validateConfiguration(Configuration configuration, AgentInfo agentInfo)
      throws ValidationException {
    parseConfiguration(configuration);
  }

  @Override
  public Command createCommand(
      int commandId,
      AgentInfo agentInfo,
      Configuration configuration,
      CommandContext commandContext)
      throws ValidationException, InitializationException {
    EchoConfigurationFile echoConfiguration = parseConfiguration(configuration);
    return new EchoCommandOngoingFile(agentInfo, echoConfiguration);
  }

  private ValidationException quickValidationError(String outerMessage, String field, String message) throws ValidationException {
    return new ValidationException(
        outerMessage,
        List.of(
            new ValidationViolation(
                field, message, ValidationViolation.ViolationType.ERROR)));
  }

  private EchoConfigurationFile parseConfiguration(Configuration configuration)
      throws ValidationException {
    if (!(configuration instanceof MultipartConfiguration multipartConfiguration)) {
      throw quickValidationError(
          "Configuration must be a Multipart object",
          "configuration",
          "must be Multipart object");
    }

    EchoConfigurationFile echoConfigurationFile;    

    try {
      echoConfigurationFile =  OBJECT_MAPPER.readValue(multipartConfiguration.jsonConfiguration().toJSON(), EchoConfigurationFile.class);

      if (echoConfigurationFile == null) {
        throw quickValidationError("Invalid configuration", "configuration", "must be a JSON object");
      }
      if (echoConfigurationFile.lines() != null && echoConfigurationFile.lines() < 1) {
        throw quickValidationError("Invalid configuration", "lines", "must be positive");
      }

      List<FilePart> files = multipartConfiguration.getFilesWithName("echos");
      if (files.size() != 1) {
        throw quickValidationError("Failed to load file from configuration", "echos", "No file");
      }
      
      return echoConfigurationFile.withFile(files.getFirst().readAllBytes());
    } catch (JacksonException e) {
      throw quickValidationError(
          "Failed to parse configuration JSON",
          "configuration",
          "error while parsing configuration JSON: %s".formatted(e.getMessage()));
    }catch (IOException echos) {
      throw quickValidationError("Failed to read file from configuration", "echos", "Cannot read file");
    }
  }
}
