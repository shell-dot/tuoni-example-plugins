package com.example.tuoni.payload;

import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.payload.Payload;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadType;
import java.nio.ByteBuffer;

public class TemplatePayload implements Payload {

  @Override
  public String getFileName() {
    // TODO: Choose the output filename and format.
    return "template-payload.exe";
  }

  @Override
  public PayloadType getPayloadType() {
    return TemplatePayloadTemplate.TYPE;
  }

  @Override
  public ByteBuffer serialize() throws SerializationException {
    throw new SerializationException("TODO: Implement payload serialization.");
  }
}
