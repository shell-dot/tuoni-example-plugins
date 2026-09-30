---
name: listener-conf
description: Implement a user's configuration fields for a Tuoni listener plugin, including Java schema and validation plus payload delivery to every supported exec-unit.
---

# Listener configuration

Before editing, read the plugin-root `AGENTS.md` and `CLAUDE.md` when present, including their referenced project context and applicable instructions. Follow the [context maintenance guide](../../../docs/project-context.md) to create missing context and preserve the existing organization. Verify recorded facts against the files you change.

**Exec-unit safety is mandatory.** The host may unload the code immediately when `Main` / `run` returns. Never crash, stop, or terminate the host process. Contain failures, and leave no invocation-owned thread, task, timer, queued work, or callback running or callable after return. Cancel, unblock, unregister, drain, and join/await before releasing shared state. Detaching a worker, marking it as background, or timing out its wait does not prove completion. When changing exec-unit code, read and apply the [host process and unload requirements](../../../docs/native-runtime.md#host-process-and-unload-requirements), including their verification checks.

Before finishing this skill, create or update that project context, including after partial work. Record the implemented schema fields/defaults/validation, configuration classes and codec paths, payload fields/encoding and versioning, startup/update behavior, platforms changed, checks performed, artifact freshness, and remaining limitations. Link a detailed contract when one exists.

Use this skill in the plugin root containing `java-plugin/` and `exec-code/`. Add or change the fields, defaults, and validation rules requested by the user. Reuse existing configuration classes and codecs; preserve unrequested fields, defaults, behavior, result formatting, and established payload fields. If a rule is unspecified, choose a sensible rule from the field's purpose and document it.

Work in this order: classify each field as Java-only/native/both -> schema and typed validation -> factory/constructor -> shared Java encoder -> every native decoder -> cross-language verification. Use [the small contract](../../../docs/implementation-recipes.md#record-the-small-contract) to distinguish bind endpoints from advertised endpoints and record field order or names, type, and units. Implement requested startup fields first; read update guidance when a field must change on a running listener.

Inventory every exec-unit implementation under `exec-code/` and reconcile it with the Java support declarations. Implement the change in all existing OS/architecture implementations unless the user limits the scope. Read the [IPC reference](../../../docs/execunit-ipc.md) when changing native configuration exchange or callbacks, and the [build guide](../../../docs/building.md) when adding dependencies or verifying artifacts.

Read the [existing listener configuration patterns](../../../docs/existing-plugins.md#configuration-and-updates). Separate Java-only settings from fields sent to exec-units, including bind endpoints versus advertised endpoints. For each live-updatable field, trace serialization, delivery, native callback, candidate validation, and active-state replacement; successful decoding alone does not prove the field changed.

## Java plugin

Find the current Java package under `java-plugin/src/main/java/`. For this plugin, update these files under `com/example/tuoni/listener/`:

For a new parser/codec, read the copied [configuration implementation guide](../../../docs/configuration.md): it gives the factory-to-native data flow, verified SDK validation/upload APIs, a Java binary encoder example, and the matching C#/C++ decoder integration points. Its sample fields/layouts are examples; retain this plugin's established contract.

- `TemplateConfigurationSchema.java`: extend `jsonSchema()` with Draft 2020-12 properties, required fields, bounds, formats, and the requested unknown-property policy. Schema defaults and formats do not themselves enforce runtime behavior; apply the same defaults and checks in Java.
- Reuse or create `TemplateListenerConfiguration.java` (or the current listener's equivalent) as the typed configuration class. Parse `JsonConfiguration.toJSON()`, or `MultipartConfiguration.jsonConfiguration().toJSON()` plus its file parts. Reject malformed or unsupported input with field-specific `ValidationException`. Keep required values, ranges, cross-field checks, and defaults consistent with the schema, including the distinction between omitted, null, and zero values.
- For uploads, set `fileSchemas()` and consume the matching `MultipartConfiguration` file parts. Define the size limits and how file bytes and required metadata reach the native configuration; describing a file in the schema alone does not transmit it.
- If parsing uses Jackson or another library, update `java-plugin/build.gradle.kts` with the matching dependency and bundle its runtime dependencies in the distributable JAR as described in the build guide. The SDK supplies no JSON parser.
- `TemplateListenerPlugin.java`: make `validateConfiguration` and `create` use the same typed parser and pass validated configuration to the listener. Remove unconditional validation TODO exceptions, including when the schema has no fields: a valid empty configuration must permit creation.
- `TemplateListener.java`: retain the typed configuration and serialize it consistently in `generateExecUnit` and `generateShellCode`. Preserve resource selection and pipe-name replacement. When Java reconfiguration is supported or requested, validate a candidate before changing state; apply or restart affected resources and retain or restore the previous working state on failure. If unsupported, replace its TODO with an explanatory `ExecutionException` and leave active state unchanged.
- For supported native updates, `serializeUpdatedConfiguration` validates and encodes using the same rules as startup without changing active state as a side effect. Its SDK signature permits `SerializationException`, not `ValidationException`; wrap validation failures in the permitted exception with a useful message/cause. Trace actual host/transport delivery to native receivers as described in the IPC reference; encoding bytes alone is not a live update. If native updates are unsupported, throw an explanatory `SerializationException` instead of a TODO or empty successful buffer. Preserve any existing update support.

In a fresh template, make these concrete handoff edits:

1. In `TemplateListenerPlugin.create`, replace the validate-then-pass-raw sequence with a call to the typed parser and pass its result to `new TemplateListener(...)`. Keep `validateConfiguration` calling that same parser.
2. Change the `TemplateListener` constructor's configuration parameter to the typed class and assign an instance field. Add one shared `serializeConfiguration()` helper that encodes that field (one immutable snapshot if updates are supported).
3. Replace `.configuration(ByteBuffer.allocate(0))` in `generateExecUnit` with `.configuration(serializeConfiguration())`.
4. Replace only the second argument, currently `ByteBuffer.allocate(0)`, in `new ShellCodeWithConf(...)` inside `generateShellCode` with `serializeConfiguration()`. Both paths must receive the same inner payload bytes; leave native resource selection and IPC framing with their existing owners.

For live updates, register `SetCallback` / `setCallback` only after verifying the host event's semantics, or connect the decoder to the plugin's existing control transport. Set receivers up before incoming updates can be lost, and synchronize initialization with updates. Decode into a complete candidate, validate it, then replace active configuration atomically or restart affected resources. Define whether updates are patches or full replacements. Honor explicit user restrictions; if live delivery is unavailable, make that limitation explicit without silently reporting success.

Choose a straightforward payload format for the requested configuration, application data, or telemetry: UTF-8 text/JSON or explicit binary fields, with matching Java and native encoders/decoders. Use Java standard APIs for text/binary; declare and bundle a JSON parser when needed. Keep plugin payload bytes separate from the native helper's host-controlled IPC framing; see [payload boundaries](../../../docs/execunit-ipc.md#plugin-payloads-and-host-ipc).

## Payload contract

Document field names or order, string encoding, numeric width/signedness/byte order, units, maximum sizes, and empty values beside the codec or in `README.md`. Preserve established meanings and widths when extending a contract. Define optional, repeated, null, and unknown-field handling, and distinguish full replacement from partial updates. Use versioning when required for compatibility; update Java and every native decoder together for incompatible changes.

Return a fresh readable `ByteBuffer` or an independent duplicate for each serialization call. Reject truncated lengths, oversized values, duplicate singleton fields, invalid encodings, and invalid required values before publishing configuration. Validate the complete payload, including any declared lengths and trailing bytes, before using decoded values.

## Exec-units

Use the [native startup and method map](../../../docs/native-runtime.md) for exact helper files, initialization ownership, and configuration-failure reporting.

Implement every exec-unit found in the inventory, including source implementations missing from the advertised list. Reconcile that discrepancy without dropping an implementation merely to avoid work. Apply the same configuration semantics to additional platforms beyond the Windows/Linux paths below.

- Windows: extend the existing typed configuration/parser, or create `exec-code/win/Configuration.cs` and add it to `exec-code/win/listener-execunit.csproj`. Call it from `exec-code/win/Program.cs` before behavior starts. Implement remaining helper stubs according to the IPC reference, retain the connection for subsequent messages, and keep `QQQWWWEEE` as the pipe-name placeholder.
- Linux: extend or create a typed configuration parser beside `exec-code/linux/listener/Main.cpp`, include new `.cpp` sources in `exec-code/linux/build_linux.sh`, and parse `CommunicationNamedPipes::connect()` bytes before behavior starts. Update the shared helpers where needed to implement validated framing and failure handling.

Test Java validation and factory creation with valid input, including `{}` when no fields are required, and malformed/invalid cases. Verify both Java generation paths against every native startup decoder. When updates are supported or requested, verify active values after delivery, a rejected update, and a resource-restart failure to confirm the previous working configuration is retained or restored. Follow the build guide for compilation, rebuilding affected native resources, dependency packaging, and final JAR comparisons. Report unavailable checks and behavior TODOs outside the configuration request.
