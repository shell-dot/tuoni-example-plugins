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
    // Tuoni supplies this context before reading the payload templates. Use its configuration
    // and managers to prepare resources shared by builds, such as binary-template loaders or
    // plugin settings, and retain dependencies that your templates need. Fail with
    // InitializationException when required resources cannot be prepared; generate individual
    // payloads later in createPayload()/serialize(), using each request's configuration.
  }

  @Override
  public List<? extends PayloadTemplate> getPayloadTemplates() {
    // Return every payload template that this plugin exposes after initialization. Tuoni reads
    // and caches this list; construct templates with any shared loaders/context prepared by
    // init(), and expose separate templates when target platforms or build contracts differ.
    return List.of(new TemplatePayloadTemplate());
  }
}
