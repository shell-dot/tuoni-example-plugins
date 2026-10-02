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
    // TODO: Parse and validate the configuration against your schema.
    // Read the user JSON and declared file attachments into a complete candidate,
    // applying the same defaults, types, required fields, ranges, and relationships
    // advertised by TemplateConfigurationSchema. Validate both Java transport
    // settings and values destined for native exec-units before acquiring resources.
    // Reuse this parser for creation and updates; report malformed or unsupported
    // values as ValidationException with useful field details and the original
    // cause. Do not mutate a running listener while validating a candidate.
    throw new ValidationException("TODO: Implement listener configuration validation.");
  }
}
