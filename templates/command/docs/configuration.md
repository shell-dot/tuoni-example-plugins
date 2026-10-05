# Configuration implementation guide

Choose a payload representation suited to the requested data. User configuration JSON is a server input format; the native payload need not be JSON. Plain UTF-8 suits one string, JSON can carry structured data when each platform has a declared parser, and a small documented binary layout can avoid native parser dependencies. No format is mandatory. Java supplies the inner bytes; the SDK/agent and native helper own [pipe framing](execunit-ipc.md#payload-boundary).

The [default configuration](../README.md#default-behavior) is already implemented: `validateConfiguration` accepts `{}` with JSON whitespace or multipart JSON without files; extra fields, other values, malformed JSON, and uploads fail validation. The existing shared `serializeConfiguration()` returns fresh zero-length buffers for both generation paths. No typed class or parser dependency is needed until fields are added.

## Follow one typed value through the plugin

For files under `java-plugin/src/main/java/com/example/tuoni/command/`:

1. `TemplateCommandConfiguration.fromConfiguration(Configuration)` parses and validates one typed value. `TemplateCommandTemplate.validateConfiguration` calls the same parser.
2. `TemplateCommandTemplate.createCommand` parses once for creation and passes that value to `new TemplateCommand(commandId, agentInfo, parsed, commandContext)`.
3. Change the command constructor from raw SDK `Configuration` to the typed class; store it in an immutable field.
4. Extend the existing shared `serializeConfiguration()` encoder to return the typed payload in a fresh readable `ByteBuffer`.
5. In `generateExecUnit`, keep `.configuration(serializeConfiguration())` and extend the existing shared encoder.
6. In `generateShellCode`, keep the second `ShellCodeWithConf` argument using that same encoder. Preserve resource selection and pipe-name patching.
7. Decode the bytes returned by managed Windows `Connect()`, supplied to the Windows native `runCommand` callback after `TryConnect`, and returned by Linux `connect()` before running the operation. Native connection failure must be distinguishable from a valid empty payload.
8. Implement `serializeCommandUpdate` only when requested. Validate a candidate before encoding it; apply it atomically in native code and retain old state on rejection. Document whether it is a patch or complete replacement.

Validation creates no runtime resources. Both generation methods send the same inner representation and independently readable buffers; Java does not add pipe headers. A command without user fields must accept a valid empty object and can send an empty payload. Do not copy the sample fields below into that command.

## Strict JSON validation with the SDK

The following Java 21 example uses Jackson 3 (`tools.jackson.*`), with its declared and bundled dependencies from [building.md](building.md#java-dependencies-and-compilation). The SDK supplies no JSON parser. Rename `ExampleConfiguration` to the command's typed class.

Its JSON schema requires integer `attempts` (1..1000), accepts optional boolean `enabled` (default false), and rejects unknown fields. The native payload is an illustrative **five-byte** layout: a four-byte little-endian attempts value followed by byte `0` or `1`. These fields and this layout are examples, not defaults for every command.

```java
import com.shelldot.tuoni.plugin.sdk.common.configuration.Configuration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.JsonConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.configuration.MultipartConfiguration;
import com.shelldot.tuoni.plugin.sdk.common.exceptions.ValidationException;
import com.shelldot.tuoni.plugin.sdk.common.validation.ValidationViolation;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.List;
import tools.jackson.core.JacksonException;
import tools.jackson.core.StreamReadFeature;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

record ExampleConfiguration(int attempts, boolean enabled) {
  private static final JsonMapper JSON = JsonMapper.builder()
      .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
      .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
      .build();

  ExampleConfiguration {
    if (attempts < 1 || attempts > 1000) {
      throw new IllegalArgumentException("attempts outside 1..1000");
    }
  }

  static ValidationException invalid(String field, String message) {
    return new ValidationException("Invalid configuration", List.of(
        new ValidationViolation(field, message, ValidationViolation.ViolationType.ERROR)));
  }

  static ExampleConfiguration fromConfiguration(Configuration raw)
      throws ValidationException {
    JsonConfiguration json;
    if (raw instanceof JsonConfiguration value) {
      json = value;
    } else if (raw instanceof MultipartConfiguration multipart) {
      // This example has no uploads. Replace this rule when adding file fields.
      if (!multipart.files().isEmpty()) {
        throw invalid("files", "File uploads are not supported");
      }
      json = multipart.jsonConfiguration();
    } else {
      throw invalid("configuration", "Expected JSON configuration");
    }
    String jsonText = json == null ? null : json.toJSON();
    if (jsonText == null) {
      throw invalid("configuration", "Expected a JSON object");
    }

    JsonNode root;
    try {
      root = JSON.readTree(jsonText);
    } catch (JacksonException error) {
      throw new ValidationException("Malformed configuration JSON", error, List.of(
          new ValidationViolation("configuration", "Must contain one valid JSON object",
              ValidationViolation.ViolationType.ERROR)));
    }
    if (root == null || !root.isObject()) {
      throw invalid("configuration", "Expected a JSON object");
    }
    for (String name : root.propertyNames()) {
      if (!name.equals("attempts") && !name.equals("enabled")) {
        throw invalid(name, "Unknown field");
      }
    }
    JsonNode attempts = root.get("attempts");
    if (attempts == null || !attempts.isIntegralNumber() || !attempts.canConvertToInt()
        || attempts.intValue() < 1 || attempts.intValue() > 1000) {
      throw invalid("attempts", "Required integer between 1 and 1000");
    }
    JsonNode enabled = root.get("enabled");
    if (enabled != null && !enabled.isBoolean()) {
      throw invalid("enabled", "Expected a boolean");
    }
    return new ExampleConfiguration(attempts.intValue(),
        enabled != null && enabled.booleanValue());
  }

  ByteBuffer toPayload() {
    return ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN)
        .putInt(attempts).put((byte) (enabled ? 1 : 0)).flip();
  }
}
```

Apply the same checks and defaults in `TemplateConfigurationSchema.jsonSchema()`. Do not rely on deserializing missing values into Java primitives: missing, null, and zero must keep their distinct meanings. For string fields, encode UTF-8 bytes and document whether limits count bytes or characters. Use a strict UTF-8 decoder on native input. A no-field schema needs its own valid empty typed value; do not make this example's `attempts` field required in unrelated plugins.

SDK `JsonConfiguration` is an interface, not a JSON object class. A small valid example can use `JsonConfiguration json = () -> "{\"attempts\":3,\"enabled\":true}";`. Command example entries use `new NamedConfiguration("example", json)`. Reject SDK configuration types the plugin does not implement rather than casting blindly.

## File uploads, when requested

`TemplateConfigurationSchema.fileSchemas()` can return `List.of(new ConfigurationSchema.FileSchema("attachment", "Input file", true))`. Its constructor takes only name, description, and required status; file-count/type/size limits need explicit Java validation. Multipart lookup uses `getFilesWithName("attachment")`, which returns `List<FilePart>`. Do not invent a `getFile()` API.

Adapt this method into the typed parser when an upload is requested, replacing the sample's no-upload rejection. The sample limit is 1 MiB; choose the actual limit from the request/protocol. Add imports for `com.shelldot.tuoni.plugin.sdk.common.configuration.FilePart`, `java.io.IOException`, and `java.io.InputStream` plus the configuration/validation imports used above.

```java
static byte[] readRequiredUpload(Configuration raw) throws ValidationException {
  final int maximumBytes = 1024 * 1024;
  if (!(raw instanceof MultipartConfiguration multipart)) {
    throw ExampleConfiguration.invalid("attachment", "Expected a file upload");
  }
  List<FilePart> files = multipart.getFilesWithName("attachment");
  if (files.size() != 1) {
    throw ExampleConfiguration.invalid("attachment", "Expected exactly one file");
  }
  FilePart file = files.getFirst();
  try {
    if (file.getSize() > maximumBytes) {
      throw ExampleConfiguration.invalid("attachment", "File exceeds size limit");
    }
    try (InputStream stream = file.openInputStream()) {
      byte[] bytes = stream.readNBytes(maximumBytes + 1);
      if (bytes.length > maximumBytes) {
        throw ExampleConfiguration.invalid("attachment", "File exceeds size limit");
      }
      return bytes;
    }
  } catch (IOException error) {
    throw new ValidationException("Could not read attachment", error, List.of(
        new ValidationViolation("attachment", "File could not be read",
            ValidationViolation.ViolationType.ERROR)));
  }
}
```

Validate other multipart names and file-count rules as required; explicitly decide whether an empty file is allowed. `getSize()` is an early check, while the bounded read enforces the actual limit. Store owned file bytes in the typed value and define how bytes and any needed metadata are encoded in the payload. File names or IDs alone do not deliver the file. Extend every native decoder and the Java schema together.


## Native decoding of the five-byte example

For JSON `{"attempts":3,"enabled":true}`, the inner payload is exactly `03 00 00 00 01`. Defaulted `enabled=false` changes only the last byte to `00`. Neither Java nor the typed native decoder processes the host envelope.

Managed Windows (.NET Framework 4.6.2): place the decoder in `Configuration.cs` and add that file to the explicit `.csproj` source list. For the five-byte sample:

```csharp
if (bytes == null || bytes.Length != 5)
    throw new ArgumentException("Expected five configuration bytes");
uint attempts = (uint)bytes[0] | ((uint)bytes[1] << 8)
    | ((uint)bytes[2] << 16) | ((uint)bytes[3] << 24);
if (attempts < 1 || attempts > 1000 || bytes[4] > 1)
    throw new ArgumentException("Invalid attempts or enabled");
bool enabled = bytes[4] == 1;
```

Use `using System;`, store the decoded values in a typed configuration, and let the owning execution path report failure and clean up on exceptions.

Native Windows and Linux (C++11): use the same typed decoder for each C++ implementation. On Windows, decode the configuration vector supplied to the `runCommand` callback in `exec-code/win-native/command/Main.cpp`; add translation units to `exec-code/win-native/build_windows.sh` for x86/x64. On Linux, decode the vector returned by `pipe.connect()` beside `Main.cpp` and add translation units to `build_linux.sh`. Include `<cstdint>` and `<stdexcept>`:

```cpp
if (bytes.size() != 5)
    throw std::invalid_argument("Expected five configuration bytes");
const std::uint32_t attempts = std::uint32_t(bytes[0])
    | (std::uint32_t(bytes[1]) << 8)
    | (std::uint32_t(bytes[2]) << 16)
    | (std::uint32_t(bytes[3]) << 24);
if (attempts < 1 || attempts > 1000 || bytes[4] > 1)
    throw std::invalid_argument("Invalid attempts or enabled");
const bool enabled = bytes[4] == 1;
```

Catch exceptions before they leave `start`, `run`, or a worker callback. Variable-length binary formats additionally need checked lengths/offsets and bounds before allocating. Define endianness, width, signedness, units and maximum lengths beside the actual encoder.

## UTF-8 payloads

For a text payload, encode the validated Java string directly. The standard-library strict encoder rejects unpaired UTF-16 surrogates:

```java
static ByteBuffer encodeText(String value) throws SerializationException {
  try {
    return StandardCharsets.UTF_8.newEncoder()
        .onMalformedInput(CodingErrorAction.REPORT)
        .onUnmappableCharacter(CodingErrorAction.REPORT)
        .encode(CharBuffer.wrap(value));
  } catch (CharacterCodingException error) {
    throw new SerializationException("Malformed text configuration", error);
  }
}
```

Import `ByteBuffer`/`CharBuffer` from `java.nio`, the used `java.nio.charset` types, and SDK `common.exceptions.SerializationException`. Validate encoded-byte limits during configuration parsing too, reporting a field-specific `ValidationException`. JSON Schema character limits are not UTF-8 byte limits.

In C#, `new System.Text.UTF8Encoding(false, true).GetString(bytes)` rejects malformed UTF-8. C++11 can retain bytes in `std::string` or `std::vector<uint8_t>`; when interpreting them as text, use a validated UTF-8 reader or a small checked implementation, not locale-dependent conversion. An echo can preserve the already validated bytes unchanged. No terminator is added unless the agreed payload explicitly requires one.

## Verify the complete handoff

Apply the [Java artifact and initialization gate](java-verification.md) whenever this configuration work introduces or changes Java code/dependencies. Verify the exported JAR contains the parser and its transitive runtime classes, including `tools/jackson/core/JacksonException.class` for Jackson 3, then exercise real provider initialization and valid/invalid factory calls with an isolated loader. Tests against Gradle's normal runtime classpath do not establish that the delivered JAR can load.

Apply the [byte-verification gate](payload-verification.md) before declaring this handoff complete. Assert position zero and exact payload limit on both Java generation paths and supported updates. Test real Java-produced bytes against every native decoder, then through the actual native connection helper with verified startup framing; parser-only fixtures bypass that failure-prone boundary. Check a native response through the real Java receiver as well.

Verify factory creation with valid/invalid JSON and each decoder against the agreed bytes. For the five-byte example include defaulted false, minimum/maximum attempts, wrong lengths and invalid boolean values. For text include Unicode, empty text when allowed, malformed encodings and the byte limit. For uploads verify both metadata and actual bytes arrive, including the accepted empty-file case.

Exercise both generation methods: equal payload bytes and independent buffer positions should emerge. Run native result fixtures through Java to check the return path. `validateConfiguration`, `createCommand` and supported updates report field errors as `ValidationException`; encoding/resource failures use `SerializationException`. Keep unavailable platform/runtime checks explicit.
