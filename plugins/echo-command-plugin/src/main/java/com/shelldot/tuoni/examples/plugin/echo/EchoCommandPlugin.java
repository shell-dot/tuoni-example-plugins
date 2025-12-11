package com.shelldot.tuoni.examples.plugin.echo;

import com.shelldot.tuoni.plugin.sdk.command.CommandPlugin;
import com.shelldot.tuoni.plugin.sdk.command.CommandPluginContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandTemplate;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import java.util.List;

public class EchoCommandPlugin implements CommandPlugin {

  private volatile boolean initialized = false;
  private volatile List<CommandTemplate> cachedCommandTemplates = List.of();

  @Override
  public void init(CommandPluginContext pluginContext) throws InitializationException {
    if (this.initialized) {
      return;
    }
    this.initialized = true;
    this.cachedCommandTemplates = List.of(new EchoCommandTemplate(pluginContext), new EchoCommandOngoingTemplate(pluginContext), new EchoCommandOngoingFileTemplate(pluginContext));
  }

  @Override
  public List<? extends CommandTemplate> getCommandTemplates() {
    return cachedCommandTemplates;
  }
}
