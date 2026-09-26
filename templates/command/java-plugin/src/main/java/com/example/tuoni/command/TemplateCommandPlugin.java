package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.command.CommandPlugin;
import com.shelldot.tuoni.plugin.sdk.command.CommandPluginContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandTemplate;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import java.util.List;

public class TemplateCommandPlugin implements CommandPlugin {

  @Override
  public void init(CommandPluginContext pluginContext) throws InitializationException {
    // TODO: Initialize any plugin-wide resources here.
  }

  @Override
  public List<? extends CommandTemplate> getCommandTemplates() {
    return List.of(new TemplateCommandTemplate());
  }
}
