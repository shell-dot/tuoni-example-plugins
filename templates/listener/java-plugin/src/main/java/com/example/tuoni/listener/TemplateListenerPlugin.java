package com.example.tuoni.listener;

import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.listener.Listener;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerContext;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerPlugin;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerPluginContext;

public class TemplateListenerPlugin implements ListenerPlugin {

  @Override
  public void init(ListenerPluginContext pluginContext) throws InitializationException {
    // TODO: Initialize any plugin-wide resources here.
  }

  @Override
  public ConfigurationSchema getConfigurationSchema() {
    return new TemplateConfigurationSchema();
  }

  @Override
  public Listener create(
      long listenerId, Configuration configuration, ListenerContext listenerContext)
      throws InitializationException, ValidationException {
    validateConfiguration(configuration);
    return new TemplateListener(listenerId, configuration, listenerContext);
  }

  static void validateConfiguration(Configuration configuration) throws ValidationException {
    // TODO: Parse and validate the configuration against your schema.
    throw new ValidationException("TODO: Implement listener configuration validation.");
  }
}
