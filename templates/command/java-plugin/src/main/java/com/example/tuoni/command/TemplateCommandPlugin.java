package com.example.tuoni.command;

import com.shelldot.tuoni.plugin.sdk.command.CommandPlugin;
import com.shelldot.tuoni.plugin.sdk.command.CommandPluginContext;
import com.shelldot.tuoni.plugin.sdk.command.CommandTemplate;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import java.util.List;

public class TemplateCommandPlugin implements CommandPlugin {

  @Override
  public void init(CommandPluginContext pluginContext) throws InitializationException {
    // The default command requires no plugin-wide initialization.
    // The host provides pluginContext when loading this provider. Initialize shared
    // services required by all its command templates here and retain the context only
    // if needed. Keep command-specific configuration and mutable execution state in
    // each TemplateCommand. Report provider setup failures as InitializationException;
    // if no shared setup is required, this method can intentionally remain empty.
  }

  @Override
  public List<? extends CommandTemplate> getCommandTemplates() {
    // Expose this provider's command templates for host discovery. Add one instance
    // for each implemented command name; a template may serve many invocations, so
    // invocation-specific mutable state belongs in the command created by its factory.
    return List.of(new TemplateCommandTemplate());
  }
}
