package com.example.tuoni.payload;

import com.shelldot.tuoni.plugin.sdk.common.exceptions.InitializationException;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadPlugin;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadPluginContext;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadTemplate;
import java.util.List;

public class TemplatePayloadPlugin implements PayloadPlugin {

  @Override
  public void init(PayloadPluginContext pluginContext) throws InitializationException {
    // TODO: Initialize any plugin-wide resources here.
  }

  @Override
  public List<? extends PayloadTemplate> getPayloadTemplates() {
    return List.of(new TemplatePayloadTemplate());
  }
}
