package com.example.tuoni.listener;

import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.configuration.JsonConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.MultipartConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.NamedConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.listener.Listener;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerContext;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerPlugin;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerPluginContext;
import java.util.List;

public class TemplateListenerPlugin implements ListenerPlugin {

  @Override
  public void init(ListenerPluginContext pluginContext) throws InitializationException {
    // The idle template requires no plugin-wide resources.
    // Retain services from pluginContext only when instances need them, and prepare
    // shared immutable settings or helpers used by every listener from this plugin.
    // Keep per-listener sockets, sessions, and workers in TemplateListener instead.
    // Release partially acquired resources and wrap initialization failures with
    // their cause in InitializationException. Schema lookup must also work before
    // this hook runs, so do not make schema metadata depend on initialized state.
  }

  @Override
  public ConfigurationSchema getConfigurationSchema() {
    return new TemplateConfigurationSchema();
  }

  @Override
  public List<NamedConfiguration> getExampleConfigurations() {
    JsonConfiguration empty = () -> "{}";
    return List.of(new NamedConfiguration("default", empty));
  }

  @Override
  public Listener create(
      long listenerId, Configuration configuration, ListenerContext listenerContext)
      throws InitializationException, ValidationException {
    // Validate the candidate before constructing a listener associated with this
    // stable listenerId and the supplied SDK context. Pass parsed configuration
    // to the instance when a typed model is introduced, keeping factory and
    // reconfiguration validation consistent. Construction must not start the
    // transport; resource acquisition belongs to the listener's start() lifecycle.
    validateConfiguration(configuration);
    return new TemplateListener(listenerId, configuration, listenerContext);
  }

  static void validateConfiguration(Configuration configuration) throws ValidationException {
    JsonConfiguration json;
    if (configuration instanceof JsonConfiguration value) {
      json = value;
    } else if (configuration instanceof MultipartConfiguration multipart) {
      if (!multipart.files().isEmpty()) {
        throw new ValidationException("The template listener does not accept file uploads.");
      }
      json = multipart.jsonConfiguration();
    } else {
      throw new ValidationException("Expected an empty JSON object: {}.");
    }
    String text = json == null ? null : json.toJSON();
    // Complete grammar for the current empty-object schema; add a typed parser
    // when introducing fields for the TODO traffic channel.
    if (text == null || !text.matches("[ \\t\\r\\n]*\\{[ \\t\\r\\n]*\\}[ \\t\\r\\n]*")) {
      throw new ValidationException("The template listener accepts only an empty JSON object: {}.");
    }
  }
}
