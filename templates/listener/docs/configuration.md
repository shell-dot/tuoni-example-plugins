# Configuration implementation guide

Use this when creating a configuration parser/codec or wiring it into the template. Adapt the examples to the user's requested fields; the example names, values, layouts, and limits are not mandatory plugin settings. Extend an existing contract without changing established field meanings or replacing working parsers. See [IPC framing](execunit-ipc.md) for the outer agent protocol and [build requirements](building.md) for dependencies and packaging.

Parse user configuration in Java and pass a validated typed value into the listener. Choose a straightforward native payload encoding for the requested fields: UTF-8 text/JSON or explicit binary fields. Java uses standard text/binary APIs; add a declared bundled JSON parser when needed. The native helper owns the [host IPC envelope](execunit-ipc.md#plugin-payloads-and-host-ipc); keep it separate from plugin configuration bytes.

Sections: [Java handoff](#follow-one-typed-value-through-the-plugin), [JSON validation](#strict-json-validation-with-the-sdk), [uploads](#file-uploads-when-requested), [payload and native decoders](#worked-binary-payload-and-native-decoders), [verification](#verify-the-complete-handoff).

The [idle default](../README.md#default-behavior) already validates `{}` with JSON whitespace or multipart JSON without files and rejects fields, other values, malformed JSON, and uploads. The shared `serializeConfiguration()` returns fresh zero-length buffers for both startup methods and valid replacement serialization; all managed/native entrypoints require zero payload bytes. Java empty replacement preserves the same instance/status. Encoding a no-field replacement is valid and does not claim native update delivery.

## Choose the payload format

Use the format that makes this task easy to implement correctly across its consumers. A single value may need only UTF-8 text. JSON is useful for named optional fields when each native implementation has a suitable parser; do not assume the SDK or native template provides one. Explicit binary fields are useful for a small fixed set of numeric values or opaque bytes. Preserve an established peer contract when extending an existing listener.

Document field names or order, sizes, integer signedness/byte order, units, maximum payload size, empty/omitted values, and update semantics. Add versioning when needed for compatibility. The five-byte example below is only an illustration; its fields and layout are not requirements for unrelated listeners.

## Follow one typed value through the plugin

For files under `java-plugin/src/main/java/com/example/tuoni/listener/`:

1. `TemplateListenerConfiguration.fromConfiguration(Configuration)` parses and validates; it returns the typed value. `TemplateListenerPlugin.validateConfiguration` calls it and discards the result.
2. `TemplateListenerPlugin.create` calls the same parser, then passes its result to `new TemplateListener(listenerId, parsed, listenerContext)`.
3. Change the `TemplateListener` constructor's configuration parameter from SDK `Configuration` to `TemplateListenerConfiguration`; store it in a typed field.
4. Extend the existing shared `serializeConfiguration()` helper to encode the typed value, for example by returning `configuration.toBytes()`.
5. In `generateExecUnit`, keep `.configuration(serializeConfiguration())` and extend the existing shared encoder.
6. In `generateShellCode`, keep the second `new ShellCodeWithConf(...)` argument using that shared `serializeConfiguration()` encoder.
7. When Java reconfiguration is supported or requested, `reconfigure` validates a candidate and applies resources before publishing the typed value. For supported native updates, `serializeUpdatedConfiguration` parses the supplied candidate and encodes it using the same rules without changing active state; follow the IPC reference for delivery and failure handling. The default already supports no-field replacement and encoding. For added fields whose reconfiguration/update capability is unsupported, throw an explanatory `ExecutionException` (`reconfigure`) or `SerializationException` (`serializeUpdatedConfiguration`) and leave active state unchanged. Do not remove existing support or implement live delivery solely because the interface has an encoding hook.

Keep validation free of resource creation. A standalone validation call may parse once, but the factory should parse once for its own creation operation and pass that typed result onward; it should not validate one object and retain a different raw object. Immutable fields or defensive copies keep later serialization consistent. With updates, serialize one complete configuration snapshot per call.

The encoder returns only the plugin's configuration bytes. The SDK/agent adds the outer IPC frame. Native `Connect()` / `connect()` strips that wrapper and returns the original bytes. Do not add a pipe length prefix or host envelope in the Java configuration encoder.

## Strict JSON validation with the SDK

This Java 21 example uses Jackson 3 (`tools.jackson.*`) for user JSON, matching the dependency recipe in the build guide, and `ByteBuffer` for a small binary native payload. Rename `ExampleConfiguration` to the plugin's actual typed class and adapt the fields. Its schema is an object with required integer `attempts` (1..1000), optional boolean `enabled` (default false), and `additionalProperties: false`. Explicit null, numeric strings, fractional attempts, duplicate properties, and trailing JSON are rejected; missing `enabled` is defaulted.

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

  ByteBuffer toBytes() {
    return ByteBuffer.allocate(5).order(ByteOrder.LITTLE_ENDIAN)
        .putInt(attempts)
        .put((byte) (enabled ? 1 : 0))
        .flip(); // Fresh readable buffer containing only plugin configuration.
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

Validate other multipart names and file-count rules as required; explicitly decide whether an empty file is allowed. `getSize()` is an early check, while the bounded read enforces the actual limit. Store owned file bytes in the typed value and define their lengths/boundaries and any needed metadata in the payload. File names or IDs alone do not deliver the file. Extend every native decoder and the Java schema together.

## Worked binary payload and native decoders

The example JSON `{"attempts":3,"enabled":true}` becomes exactly five bytes:

```text
03 00 00 00 01
```

| Offset | Meaning | Encoding |
| --- | --- | --- |
| 0..3 | Attempts, 1..1000 | Four-byte little-endian integer |
| 4 | Enabled | One byte, exactly 0 or 1 |

The maximum and minimum payload size are both five bytes for this example. Reject any different length, an out-of-range attempt count, or another boolean value. Java emits the resolved default explicitly. This payload has no host IPC header, application frame prefix, or field tags.

### Managed Windows (.NET Framework 4.6.2)

Decode the bytes returned by `pipe.Connect()` in the plugin's typed `Configuration.cs` before starting behavior. Add a new source file to `exec-code/win/listener-execunit.csproj` when needed. This example uses only platform APIs and explicit little-endian operations:

```csharp
if (bytes == null || bytes.Length != 5)
    throw new FormatException("Expected five configuration bytes");
uint attempts = (uint)bytes[0]
    | ((uint)bytes[1] << 8)
    | ((uint)bytes[2] << 16)
    | ((uint)bytes[3] << 24);
if (attempts < 1 || attempts > 1000 || bytes[4] > 1)
    throw new FormatException("Invalid configuration values");
bool enabled = bytes[4] == 1;
// Store attempts and enabled in the returned typed configuration.
```

Preserve the implemented pipe helper's host-protocol boundary; it must return the inner configuration bytes unchanged. The configuration class does not parse the outer pipe envelope.

### Native Windows and Linux (C++11)

Decode the vector returned by `pipe.connect()` in a typed configuration class beside each `Main.cpp`. For Windows native, first check `isConnected()` in `exec-code/win-native/listener/Main.cpp` and add new `.cpp` files to `exec-code/win-native/build_windows.sh` for x86/x64. For Linux, add them to `exec-code/linux/build_linux.sh`. Include `<cstdint>` and `<stdexcept>` for this example:

```cpp
if (bytes.size() != 5)
    throw std::invalid_argument("Expected five configuration bytes");
const std::uint32_t attempts = static_cast<std::uint32_t>(bytes[0])
    | (static_cast<std::uint32_t>(bytes[1]) << 8)
    | (static_cast<std::uint32_t>(bytes[2]) << 16)
    | (static_cast<std::uint32_t>(bytes[3]) << 24);
if (attempts < 1 || attempts > 1000 || bytes[4] > 1)
    throw std::invalid_argument("Invalid configuration values");
const bool enabled = bytes[4] == 1;
// Store attempts and enabled in the returned typed configuration.
```

Catch parsing failures in the native [startup/cleanup path](native-runtime.md); no C++ exception may escape exported `start` or `run`. Failed updates retain the prior typed value. Host framing and callback dispatch stay in the pipe helper.

### When a requested field is text

Use UTF-8 and document whether the payload is all text or contains a length-delimited string field. In Java, use `StandardCharsets.UTF_8.newEncoder()` / `.newDecoder()` with `CodingErrorAction.REPORT` when malformed input must be rejected. Read only the remaining buffer bytes. In C#, use `new UTF8Encoding(false, true)` for strict decoding; in C++ use a suitable strict decoder for the chosen format. Treat length limits as encoded-byte limits where required; JSON Schema string lengths count characters.

For example, `U+00E9` encodes as `c3 a9`: two bytes, one character. Test a multibyte string, an empty permitted string, the byte limit, truncated sequences, and invalid encodings. For a binary string field, define its length width/byte order and validate that length against the available bytes before slicing or allocation. Update all producers and consumers together when introducing the field.

## Verify the complete handoff

Apply the [Java artifact and initialization gate](java-verification.md) whenever this configuration work introduces or changes Java code/dependencies. Verify the exported JAR contains the parser and its transitive runtime classes, including `tools/jackson/core/JacksonException.class` for Jackson 3, then exercise real provider initialization and valid/invalid factory calls with an isolated loader. Tests against Gradle's normal runtime classpath do not establish that the delivered JAR can load.

Apply the [byte-verification gate](payload-verification.md) before declaring this handoff complete. Assert position zero and exact payload limit on both Java generation paths and supported updates. Test real Java-produced bytes against every native decoder, then through the actual native connection helper with verified startup framing; parser-only fixtures bypass that failure-prone boundary. Check a native response through the real Java receiver as well.

Verify Java encoder output and managed Windows, native Windows, and Linux decoders against the five-byte fixture when using this example. Check field values, defaulted enabled=false, minimum/maximum attempts, wrong length, out-of-range values, and invalid boolean bytes. Exercise the actual factory and both generation methods: equal inner payloads and independently readable buffers should emerge from each call. For another chosen format, make a fixture for its actual contract instead of changing it to match this example.

`serializeUpdatedConfiguration`, `generateExecUnit`, and `generateShellCode` permit `SerializationException`, not `ValidationException`. Parse initial input at the factory boundary; wrap candidate validation failures where only serialization errors are permitted, for example `throw new SerializationException("Invalid listener configuration", error);`. Do not widen the SDK method signatures or swallow the failure.
