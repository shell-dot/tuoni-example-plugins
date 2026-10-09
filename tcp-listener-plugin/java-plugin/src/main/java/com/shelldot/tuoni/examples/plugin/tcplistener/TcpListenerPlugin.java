package com.shelldot.tuoni.examples.plugin.tcplistener;

import com.shelldot.tuoni.examples.plugin.tcplistener.configuration.SimpleConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.listener.Listener;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerContext;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerPlugin;
import com.shelldot.tuoni.plugin.sdk.listener.ListenerPluginContext;

public class TcpListenerPlugin implements ListenerPlugin {

  @Override
  public void init(ListenerPluginContext pluginContext) throws InitializationException {
  }

  @Override
  public ConfigurationSchema getConfigurationSchema() throws SerializationException {
    return new SimpleConfigurationSchema(TcpListenerPluginConfiguration.JSON_SCHEMA);
  }

  @Override
  public Listener create(
      long listenerId, Configuration configuration, ListenerContext listenerContext)
      throws InitializationException, ValidationException {
    TcpListenerPluginConfiguration cfg =
        TcpListenerPluginConfiguration.fromConfiguration(configuration);
    return new TcpListener(listenerId, cfg, listenerContext);
  }
}
