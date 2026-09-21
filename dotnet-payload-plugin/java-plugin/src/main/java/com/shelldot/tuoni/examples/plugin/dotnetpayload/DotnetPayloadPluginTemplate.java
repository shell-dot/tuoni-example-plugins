package com.shelldot.tuoni.examples.plugin.dotnetpayload;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.List;

import com.shelldot.tuoni.examples.plugin.dotnetpayload.configuration.SimpleConfigurationSchema;
import com.shelldot.tuoni.examples.plugin.dotnetpayload.utils.ShellcodeUtil;
import com.shelldot.tuoni.plugin.sdk.common.Architecture;
import com.shelldot.tuoni.plugin.sdk.common.OperatingSystem;
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.ConfigurationSchema;
import com.shelldot.tuoni.plugin.sdk.common.configuration.NamedConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.SerializationException;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.payload.ListenerShellCode;
import com.shelldot.tuoni.plugin.sdk.payload.Payload;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadTemplate;
import com.shelldot.tuoni.plugin.sdk.payload.PayloadType;

public class DotnetPayloadPluginTemplate implements PayloadTemplate {

    private static final String SHELLCODE_PATH = "/templates/dotnet-agent.exe";

    @Override
    public String getName() {
        return "custom-dotnet-payload";
    }

    @Override
    public String getDescription() {
        return "Example custom .NET payload.";
    }

    @Override
    public List<NamedConfiguration> getExampleConfigurations() {
        return List.of();
    }

    @Override
    public ConfigurationSchema getConfigurationSchema() throws SerializationException {
        return new SimpleConfigurationSchema(DotnetPayloadPluginConfiguration.JSON_SCHEMA);

    }

    @Override
    public PayloadType getPayloadType() {
        return PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64);
    }

    @Override
    public void validateConfiguration(Configuration configuration)
            throws ValidationException {
    }

    @Override
    public Payload createPayload(
            long payloadId, Configuration configuration, List<ListenerShellCode> listenerShellCodes)
            throws SerializationException, ValidationException {
        ListenerShellCode listenerShellCode = listenerShellCodes.get(0);
        listenerShellCode.setAgentConfiguration(
                ByteBuffer.allocate(Long.BYTES)
                        .order(ByteOrder.LITTLE_ENDIAN)
                        .putLong(0, payloadId));
        return new DotnetPayloadImpl(listenerShellCode);
    }

    public class DotnetPayloadImpl implements Payload
    {
        ListenerShellCode listenerShellCode;

        public DotnetPayloadImpl(ListenerShellCode listenerShellCode) {
            this.listenerShellCode = listenerShellCode;
        }

        @Override
        public String getFileName() {
            return "skippy.exe";
        }

        @Override
        public PayloadType getPayloadType() {
            return PayloadType.of(OperatingSystem.WINDOWS, Architecture.X64);
        }

        public ByteBuffer serialize() throws SerializationException {
            ByteBuffer template = ShellcodeUtil.readClasspathResourceToBuffer(getClass(), SHELLCODE_PATH);
            ByteBuffer listenerTlv = listenerShellCode.serializeToTlv();
            ByteBuffer result = ByteBuffer.allocate(template.remaining() + listenerTlv.remaining());
            result.put(template);
            result.put(listenerTlv);
            result.position(0);
            return result;
        }
    }
}
