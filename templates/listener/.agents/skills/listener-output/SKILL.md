---
name: listener-output
description: Shape the data and user-facing output of a Tuoni listener across every existing exec-unit and its supported Java receive path.
---

# Listener output

Before editing, read the plugin-root `AGENTS.md` and `CLAUDE.md` when present, including their referenced project context and applicable instructions. Follow the [context maintenance guide](../../../docs/project-context.md) to create missing context and preserve the existing organization. Verify recorded facts against the files you change.

**Exec-unit safety is mandatory.** The host may unload the code immediately when `Main` / `run` returns. Never crash, stop, or terminate the host process. Contain failures, and leave no invocation-owned thread, task, timer, queued work, or callback running or callable after return. Cancel, unblock, unregister, drain, and join/await before releasing shared state. Detaching a worker, marking it as background, or timing out its wait does not prove completion. When changing exec-unit code, read and apply the [host process and unload requirements](../../../docs/native-runtime.md#host-process-and-unload-requirements), including their verification checks.

Before finishing this skill, create or update that project context, including after partial work. Record the native payload fields/encoding and sender locations, Java receiver/parser locations, streaming/version behavior, presentation surfaces and result names, platform coverage, checks performed, artifact freshness, and remaining limitations.

Use this skill from a listener plugin copied from this template when the user specifies what they want to see or receive from listener activity. Preserve the implemented listener behavior. Identify the requested output surface and the raw facts needed for it, including any status, agent metadata, traffic, files, or activity events. Infer a simple presentation for details the prompt leaves open.

Start with [the output selection table](../../../docs/implementation-recipes.md#choose-the-output-path). Work backward from the requested surface: presentation -> typed facts -> existing receiver -> native sender if needed. Java-owned endpoint/session information needs no new native message. Remote observations need a real receive path; command execution results remain owned by the command plugin after the listener forwards their opaque bytes.

Reuse existing codecs, configuration/payload contracts, and unrequested output fields. Read the [IPC and Java transport reference](../../../docs/execunit-ipc.md) to trace data delivery and the [build guide](../../../docs/building.md) for dependencies and packaging.

Inventory every implementation under `exec-code/` and the Java support methods in `TemplateListener.java`. When native output or encoding changes, update all existing exec-units unless the user limits platforms. Keep their field meanings and encoding consistent, and do not reduce advertised platform support to skip output work. A change confined to formatting existing Java state does not require a new native protocol or native rebuild.

Choose a straightforward payload format for the requested configuration, application data, or telemetry: UTF-8 text/JSON or explicit binary fields, with matching Java and native encoders/decoders. Use Java standard APIs for text/binary; declare and bundle a JSON parser when needed. Keep plugin payload bytes separate from the native helper's host-controlled IPC framing; see [payload boundaries](../../../docs/execunit-ipc.md#plugin-payloads-and-host-ipc).

Read the [existing listener receive and presentation patterns](../../../docs/existing-plugins.md#receive-state-and-presentation). Associate decoded observations with the correct listener/agent/session and retain bounded state with a defined disconnect/expiry policy. Keep transport send acknowledgement, command execution outcome, Java resource status, and observed native health distinct.

## Trace the receive path first

Find the native application transport sender and the matching Java connection handler/frame decoder. The named pipe/FIFO connects the native exec-unit to its local agent; it is not an arbitrary output channel to the Java plugin. `ExecUnitListener` has no `parseResult` callback, but this does not prevent Java from decoding its own transport. Follow the concrete flow in the reference and extend the plugin's existing transport where available.

Use the [Java implementation map](../../../docs/listener-java.md) to locate or introduce receiver/codec/model files and wire SDK request, command-queue, and send-status handling. Its presentation table lists actual listener output APIs. If native helpers or runtime ownership need work, use the [native implementation map](../../../docs/native-runtime.md).

Define the requested native facts, their typed fields, encoding, length limits, message boundaries, and Java destination before editing senders. Preserve existing opaque agent metadata/request frames. Put custom telemetry in a separate application message/field using the agreed text, JSON, or binary encoding, with versioning when existing peers need compatibility. Do not inject presentation data into SDK-owned agent payloads or substitute a summary for a requested file.

## Native senders

- In `exec-code/win/Program.cs` and its transport implementation, gather the required data and encode it for the Java receiver. Keep `exec-code/win/exec-unit-utils/` changes limited to actual local-agent IPC needs. Add new C# sources to `exec-code/win/listener-execunit.csproj`.
- In `exec-code/linux/listener/Main.cpp` and its transport implementation, send equivalent application messages to the Java receiver. Keep `exec-code/linux/common/CommunicationNamedPipes.*` aligned with the host's local-agent protocol. Add new C++ sources to `exec-code/linux/build_linux.sh`.
- Apply the same result contract to every additional exec-unit implementation discovered in the inventory, unless the user limits the scope.

## Java receive and formatting

Update the Java transport decoder and its typed data model to parse the new native messages, validating lengths, types, versions, and incomplete frames. Keep `ListenerContext.readMetadata` and the supported `Agent` APIs handling their existing SDK data. Format the decoded custom facts in Java for the requested presentation: for example `TemplateListener.getInfo()` in `java-plugin/src/main/java/com/example/tuoni/listener/TemplateListener.java`, an existing output facility, or event types supported by `ListenerContext.getActivityLogger()`. Base remote status on received observations rather than Java startup state. Preserve requested raw/downloadable data where the output facility supports it.

If the plugin has no existing native-to-Java transport, inspect its actual receive hooks and SDK capabilities before choosing a route. Explain an output limitation only after establishing that the requested data or presentation has no supported path; seek the missing transport/presentation choice then. Do not invent a listener result callback or report delivery without a receiver.

Verify every exec-unit emits the required application bytes and that its actual Java receiver parses and formats them as requested. Test normal agent traffic alongside added telemetry, malformed/incomplete frames, and compatibility where needed. Follow the build guide to compile, rebuild native resources, bundle parser dependencies, and compare final JAR entries with fresh artifacts. Report unavailable platform/runtime checks.
