package com.shelldot.tuoni.examples.plugin.dotnetpayload;

import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadPlugin;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadPluginContext;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadTemplate;
import java.util.List;

public class DotnetPayloadPlugin implements PayloadPlugin  {
  public DotnetPayloadPlugin() {}

  @Override
  public void init(PayloadPluginContext pluginContext) throws InitializationException {

  }

  @Override
  public List<? extends PayloadTemplate> getPayloadTemplates() {
    return List.of(new DotnetPayloadPluginTemplate());
  }
}
