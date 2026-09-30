---
name: command-conf
description: Implement a user's configuration fields for a Tuoni command plugin, including Java schema and validation plus payload delivery to every supported exec-unit.
---

# Command configuration

Before editing, read the plugin-root `AGENTS.md` and `CLAUDE.md` when present, including their referenced project context and applicable instructions. Follow the [context maintenance guide](../../../docs/project-context.md) to create missing context and preserve the existing organization. Verify recorded facts against the files you change.

**Exec-unit safety is mandatory.** The host may unload the code immediately when `Main` / `run` returns. Never crash, stop, or terminate the host process. Contain failures, and leave no invocation-owned thread, task, timer, queued work, or callback running or callable after return. Cancel, unblock, unregister, drain, and join/await before releasing shared state. Detaching a worker, marking it as background, or timing out its wait does not prove completion. When changing exec-unit code, read and apply the [host process and unload requirements](../../../docs/native-runtime.md#host-process-and-unload-requirements), including their verification checks.

Before finishing this skill, create or update that project context, including after partial work. Record the implemented schema fields/defaults/validation, configuration classes and codec paths, payload format and versioning, startup/update behavior, platforms changed, checks performed, artifact freshness, and remaining limitations. Link a detailed contract when one exists.

Use this skill in the plugin root containing `java-plugin/` and `exec-code/`. Add or change the fields, defaults, and validation rules requested by the user. Reuse existing configuration classes and codecs; preserve unrequested fields, defaults, behavior, result formatting, and established payload fields. If a rule is unspecified, choose a sensible rule from the field's purpose and document it.

For a fresh configuration, follow step 3 of the [minimum implementation path](../../../docs/implementation-recipes.md#minimum-path); its [one-value trace](../../../docs/implementation-recipes.md#one-value-trace) gives a small complete field contract and byte fixture. A no-input command accepts a validated empty object; do not inherit sample fields from a walkthrough. Read upload/update sections only when those features are needed.

Inventory every exec-unit implementation under `exec-code/` and reconcile it with the Java support declarations. Implement the change in all existing OS/architecture implementations unless the user limits the scope. Read the [IPC reference](../../../docs/execunit-ipc.md) when changing native configuration exchange or callbacks, and the [build guide](../../../docs/building.md) when adding dependencies or verifying artifacts.

Read the [configuration patterns from existing plugins](../../../docs/existing-plugins.md#configuration) when selecting a typed model, codec, or validation approach. Trace each field from schema/defaults through Java serialization to every native decoder; record width, signedness, units, cardinality, and omission behavior. Use standard Java byte/text APIs or an explicitly declared JSON parser; do not assume server-internal libraries are SDK APIs.

## Java plugin

Find the current Java package under `java-plugin/src/main/java/`. For this plugin, update these files under `com/example/tuoni/command/`:

For a new parser/codec, read the copied [configuration implementation guide](../../../docs/configuration.md): it gives the factory-to-native data flow, verified SDK validation/upload APIs, and Java payload examples and C#/C++ decoder integration points. Its sample fields are examples; retain this plugin's established contract.

- `TemplateConfigurationSchema.java`: extend `jsonSchema()` with Draft 2020-12 properties, required fields, bounds, formats, and the requested unknown-property policy. Schema defaults and formats do not themselves enforce runtime behavior; apply the same defaults and checks in Java.
- Reuse or create `TemplateCommandConfiguration.java` (or the current command's equivalent) as the typed configuration class. Parse `JsonConfiguration.toJSON()`, or `MultipartConfiguration.jsonConfiguration().toJSON()` plus its file parts. Reject malformed or unsupported input with field-specific `ValidationException`. Keep required values, ranges, cross-field checks, and defaults consistent with the schema, including the distinction between omitted, null, and zero values.
- For uploads, set `fileSchemas()` and consume the matching `MultipartConfiguration` file parts. Define the size limits and how file bytes and required metadata reach the native configuration; describing a file in the schema alone does not transmit it.
- If parsing uses Jackson or another library, update `java-plugin/build.gradle.kts` with the matching dependency and bundle its runtime dependencies in the distributable JAR as described in the build guide. The SDK supplies no JSON parser.
- `TemplateCommandTemplate.java`: make `validateConfiguration` and `createCommand` use the same typed parser and pass validated configuration to the command. Remove unconditional validation TODO exceptions, including when the schema has no fields: a valid empty configuration must permit creation. Keep example configurations consistent with the resulting schema.
- `TemplateCommand.java`: retain the typed configuration and serialize it consistently in `generateExecUnit` and `generateShellCode`. Preserve resource selection and pipe-name replacement. If the command accepts live updates, use the same documented contract in `serializeCommandUpdate`, register the native update callbacks described in the IPC reference, and validate before swapping active state. Retain explicit unsupported-update behavior otherwise.

In a fresh template, make these concrete handoff edits:

1. In `TemplateCommandTemplate.createCommand`, replace the validate-then-pass-raw sequence with a call to the typed parser and pass its result to `new TemplateCommand(...)`. Keep `validateConfiguration` calling that same parser.
2. Change the `TemplateCommand` constructor's configuration parameter to the typed class and assign an instance field. Add one shared `serializeConfiguration()` helper that encodes that field (one immutable snapshot if updates are supported).
3. Replace `.configuration(ByteBuffer.allocate(0))` in `generateExecUnit` with `.configuration(serializeConfiguration())`.
4. Replace only the second argument, currently `ByteBuffer.allocate(0)`, in `new ShellCodeWithConf(...)` inside `generateShellCode` with `serializeConfiguration()`. Both paths must receive the same inner payload bytes; leave native resource selection and IPC framing with their existing owners.

## Payload contract

Choose an inner payload format that fits the requested data and can be implemented with the project's actual dependencies: UTF-8 text, JSON, or a documented binary layout are common choices. Java generation methods supply only these payload bytes, and `parseResult` receives only result payload bytes. The SDK/agent and native pipe helpers own the outer framing described in the [IPC reference](../../../docs/execunit-ipc.md#payload-boundary). No Java transport-codec library is required.

Document the configuration/result fields, encoding, size bounds, omission/default behavior and any versioning needed for compatibility. For binary layouts, specify byte order, width, signedness and length units. For JSON, validate types, unknown-field policy and defaults in Java and each native reader. A no-field command can use an empty payload. Define full replacement versus partial update semantics when updates are requested, and retain the existing working state on rejected updates.

Return a fresh readable `ByteBuffer` or an independent duplicate for each serialization call. Bound payload sizes before allocation and check offsets/lengths, malformed text and invalid required values before publishing configuration. Keep error messages field-specific. Java does not add the host envelope or pipe length prefix.

## Exec-units

Use the [native startup and method map](../../../docs/native-runtime.md) for exact helper files, initialization ownership, and configuration-failure reporting.

Implement every exec-unit found in the inventory, including source implementations missing from the advertised list. Reconcile that discrepancy without dropping an implementation merely to avoid work. Apply the same configuration semantics to additional platforms beyond the Windows/Linux paths below.

- Windows: extend the existing typed configuration/parser, or create `exec-code/win/Configuration.cs` and add it to `exec-code/win/command-execunit.csproj`. Call it from `exec-code/win/Program.cs` before behavior starts. Implement remaining helper stubs according to the IPC reference, retain the connection for subsequent messages, and keep `QQQWWWEEE` as the pipe-name placeholder.
- Linux: extend or create a typed configuration parser beside `exec-code/linux/command/Main.cpp`, include new `.cpp` sources in `exec-code/linux/build_linux.sh`, and parse `CommunicationNamedPipes::connect()` bytes before behavior starts. Update the shared helpers where needed to implement validated framing and failure handling.

Test Java validation and factory creation with valid input, including `{}` when no fields are required, and malformed/invalid cases. Verify Java encoder bytes against every native decoder at startup and during supported updates. Preserve the previous working state on rejected updates. Follow the build guide for compilation, rebuilding affected native resources, dependency packaging, and comparing the final JAR entries with fresh artifacts. Report unavailable checks and behavior TODOs outside the configuration request.
