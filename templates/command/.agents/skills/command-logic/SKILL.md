---
name: command-logic
description: Implement the requested behavior of a Tuoni command plugin in every supported exec-unit, with only the result data and Java parsing needed to expose that behavior.
---

# Command logic

Before editing, read the plugin-root `AGENTS.md` and `CLAUDE.md` when present, including their referenced project context and applicable instructions. Follow the [context maintenance guide](../../../docs/project-context.md) to create missing context and preserve the existing organization. Verify recorded facts against the files you change.

**Exec-unit safety is mandatory.** The host may unload the code immediately when `Main` / `run` returns. Never crash, stop, or terminate the host process. Contain failures, and leave no invocation-owned thread, task, timer, queued work, or callback running or callable after return. Cancel, unblock, unregister, drain, and join/await before releasing shared state. Detaching a worker, marking it as background, or timing out its wait does not prove completion. When changing exec-unit code, read and apply the [host process and unload requirements](../../../docs/native-runtime.md#host-process-and-unload-requirements), including their verification checks.

Before finishing this skill, create or update that project context, including after partial work. Record implemented behavior and entry points, resource ownership and cancellation/update behavior, actual platform coverage, configuration/output contracts preserved or changed, checks performed, artifact freshness, and remaining TODOs.

Use this skill from a command plugin copied from this template. Implement the command described by the user's prompt end to end. Inventory `exec-code/` and the Java support methods (`TemplateCommandTemplate.canSendToAgent` and `TemplateCommand.supportedTypes`). Preserve any user-specified OS limits; otherwise implement the same behavior in every exec-unit present in the plugin and keep advertised support aligned. Do not narrow support to avoid an implementation. If behavior needs configuration fields that are missing, add them using the sibling [configuration skill](../command-conf/SKILL.md).

Extend existing logic and helpers instead of recreating them. Preserve configuration fields and existing payload/result formats unless the requested behavior requires a change. Read the [IPC reference](../../../docs/execunit-ipc.md) for startup, streaming, update, and stop messages, and the [build guide](../../../docs/building.md) for dependencies and artifact verification.

Use step 4 of the [minimum implementation path](../../../docs/implementation-recipes.md#minimum-path) for a fresh command. Choose the requested [behavior branches](../../../docs/implementation-recipes.md#choose-the-needed-behavior) before adding workers, cancellation callbacks or updates. The [one-value trace](../../../docs/implementation-recipes.md#one-value-trace) shows the native result calls and terminal owner; complete the used helper methods before assuming these calls work.

Choose an inner payload format that fits the requested data and can be implemented with the project's actual dependencies: UTF-8 text, JSON, or a documented binary layout are common choices. Java generation methods supply only these payload bytes, and `parseResult` receives only result payload bytes. The SDK/agent and native pipe helpers own the outer framing described in the [IPC reference](../../../docs/execunit-ipc.md#payload-boundary). No Java transport-codec library is required.

Use the [existing implementation map](../../../docs/existing-plugins.md#source-ownership-and-compatibility) to find canonical sources behind wrappers and shared imports. Check support as an OS, process architecture, exec-unit type, resource, and entrypoint combination. Keep operation and cancellation state scoped to one execution; shared templates or process-global native state must not mix concurrent commands.

## Exec-unit behavior

Read the [native implementation map](../../../docs/native-runtime.md) when replacing the skeleton or changing helpers. It identifies the methods to implement and the `Main`/pipe ownership refactor required by the Windows template.

- `exec-code/win/Program.cs`: replace the `Initialize`, `Execute`, `Complete`, and `Cleanup` placeholders with the requested behavior. Receive and validate configuration through the named pipe, keep that connection open through result and completion reporting, execute once or for the requested duration, and release resources on success, failure, or stop. Keep `QQQWWWEEE` as the pipe-name placeholder. The Windows `exec-code/win/exec-unit-utils/` classes are stubs; implement the connection, message, result, and completion methods used by this command, or replace them with working equivalents. Add any new C# source to `exec-code/win/command-execunit.csproj`.
- `exec-code/linux/command/Main.cpp`: replace the unimplemented failure path inside the exported `run(char*, char*)`. Parse and use the configuration returned by `CommunicationNamedPipes::connect()`, perform the same behavior as Windows, and close resources. Keep the `run` export. Add any new C++ source to `exec-code/linux/build_linux.sh`.

When no output contract exists yet, implement only the smallest useful result and its Java parser, such as UTF-8 text. Keep richer output already implemented by `command-output` or earlier work, and preserve all requested data. On success send results and exactly one `sendReturnSuccess`; on failure send a concise `sendError` and `sendReturnFailed`. Keep the connection alive through completion and use the IPC channel for results.

For ongoing results, send `sendConf_ongoingResult()` before streaming. If block relay is needed, configure its option and coordinate Java record/UTF-8 reassembly. For cooperative stop, advertise the grace period and register the native stop callback; register update callbacks if the behavior accepts command updates. Implement the equivalent Windows options when still absent. Use the exact IDs and encodings in the IPC reference.

## Java plugin

For result API signatures, strict UTF-8 decoding, and stateful streaming examples, read the [output guide](../../../docs/output.md) when implementing or extending result parsing.

- `java-plugin/src/main/java/com/example/tuoni/command/TemplateCommand.java`: implement `parseResult` for that exact payload format. Read only the remaining bytes of the supplied `ByteBuffer`, reject malformed data with `SerializationException`, and write the minimal useful value to `CommandResultEditor` before committing. Handle multiple result chunks or `isFinalResult` only when the behavior needs them. Keep generation, stop, and update hooks aligned with the native behavior.
- `java-plugin/src/main/java/com/example/tuoni/command/TemplateCommandTemplate.java`: make `validateConfiguration` and `createCommand` operational even when the prompt adds no fields. The fresh template rejects every configuration with a TODO exception; replace that path with real validation of the current schema, including accepting a valid empty object for a command with no fields. Preserve existing checks and pass validated configuration to the command. Update description/examples as needed; change schema fields only when required by the prompt.

Verify factory creation, including the no-fields case, before native execution. Check equivalent results and failure signals on every exec-unit, and test native result bytes through Java parsing. Exercise any streaming, update, and stop paths. Follow the build guide to compile, rebuild affected native resources, package dependencies, and compare final JAR entries against fresh artifacts. Report platform/runtime checks that could not be completed.
