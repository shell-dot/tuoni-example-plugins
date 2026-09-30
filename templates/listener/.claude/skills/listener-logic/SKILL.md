---
name: listener-logic
description: Implement the requested behavior of a Tuoni listener plugin in every supported exec-unit, with only the data flow and Java handling needed for that listener.
---

# Listener logic

Before editing, read the plugin-root `AGENTS.md` and `CLAUDE.md` when present, including their referenced project context and applicable instructions. Follow the [context maintenance guide](../../../docs/project-context.md) to create missing context and preserve the existing organization. Verify recorded facts against the files you change.

**Exec-unit safety is mandatory.** The host may unload the code immediately when `Main` / `run` returns. Never crash, stop, or terminate the host process. Contain failures, and leave no invocation-owned thread, task, timer, queued work, or callback running or callable after return. Cancel, unblock, unregister, drain, and join/await before releasing shared state. Detaching a worker, marking it as background, or timing out its wait does not prove completion. When changing exec-unit code, read and apply the [host process and unload requirements](../../../docs/native-runtime.md#host-process-and-unload-requirements), including their verification checks.

Before finishing this skill, create or update that project context, including after partial work. Record implemented behavior and entry points, resource ownership and cancellation/update behavior, actual platform coverage, configuration/output contracts preserved or changed, checks performed, artifact freshness, and remaining TODOs.

Use this skill from a listener plugin copied from this template. Implement the listener described by the user's prompt end to end. Inventory `exec-code/` and the Java support methods (`TemplateListener.getSupportedPayloadTypes` and `getSupportedExecUnitTypes`). Preserve any user-specified OS limits; otherwise implement the same behavior in every exec-unit present in the plugin and keep advertised support aligned. Do not narrow support to avoid an implementation. If behavior needs configuration fields that are missing, add them using the sibling [configuration skill](../listener-conf/SKILL.md).

Select [the transport shape](../../../docs/implementation-recipes.md#choose-the-transport-shape) first, then follow [the minimum complete path](../../../docs/implementation-recipes.md#minimum-complete-implementation). Establish local-agent IPC, implement the matching Java/native transport, prove metadata/request/command exchange, then finish shutdown and requested updates. Use [the application transport guidance](../../../docs/implementation-recipes.md#application-payloads-and-framing) to define bounded messages; existing peers retain their established contract.

Extend existing logic and helpers instead of recreating them. Preserve configuration fields, payload encoding, transport framing, and output presentation unless the prompt requires a change. Read the [IPC and Java transport reference](../../../docs/execunit-ipc.md) and use the [build guide](../../../docs/building.md) for dependencies and artifact verification.

Choose a straightforward payload format for the requested configuration, application data, or telemetry: UTF-8 text/JSON or explicit binary fields, with matching Java and native encoders/decoders. Use Java standard APIs for text/binary; declare and bundle a JSON parser when needed. Keep plugin payload bytes separate from the native helper's host-controlled IPC framing; see [payload boundaries](../../../docs/execunit-ipc.md#plugin-payloads-and-host-ipc).

Use the [existing listener patterns](../../../docs/existing-plugins.md#transport-and-lifecycle) to choose lifecycle and receive handling appropriate to the requested transport. Identify canonical native sources and the actual Java counterpart before adapting helpers. Verify each advertised OS, architecture, exec-unit type, resource, and entrypoint combination; keep connection state, pending sends, and cancellation under a clear owner.

## Exec-unit behavior

Read the [native implementation map](../../../docs/native-runtime.md) when replacing the skeleton or changing helpers. It maps helper methods and shows the ownership, failure, and cancellation changes needed around Windows `Main` and `Initialize`.

- `exec-code/win/Program.cs`: implement the requested listener transport, connection/session loop, cancellation, and cleanup. Keep the named pipe alive for the listener lifetime. Use actual host/transport cancellation and disconnect handling; the listener helper has no command-style stop message, and console Ctrl+C alone is insufficient in a native host. Keep `QQQWWWEEE` as the pipe-name placeholder. Implement remaining Windows helper stubs according to the IPC reference and add new C# sources to `exec-code/win/listener-execunit.csproj`.
- `exec-code/linux/listener/Main.cpp`: replace the scaffold inside the exported `run(char*, char*)`. Use the Linux `CommunicationNamedPipes` helper for initial configuration and the listener IPC messages, implement the same transport behavior as Windows, and close sessions and resources correctly. Keep the `run` export. Add any new C++ source to `exec-code/linux/build_linux.sh`.

For new output, add only the data handling needed by the requested behavior; preserve richer presentation already added by `listener-output`. The listener IPC functions exchange data with the local agent (`GetMetadata`, `GetDataToSend`, `NewDataFromC2` on Windows and their Linux equivalents). Implement the native-to-Java transport and its Java counterpart when the listener uses one; preserve opaque agent frames and the established application protocol. Use the reference's flow to keep these two connections distinct.

## Java plugin

Use the [Java implementation map](../../../docs/listener-java.md) for the constructor/start/stop/delete checklist, suggested receiver files when none exist, and exact SDK agent/queue/send-status calls. Wire new handlers into the owned transport lifecycle.

- `java-plugin/src/main/java/com/example/tuoni/listener/TemplateListenerPlugin.java`: make `validateConfiguration` and `create` operational, removing the unconditional TODO failure even when the prompt adds no fields. Validate the existing schema, accept valid empty configuration when appropriate, and pass the validated object to the listener.
- `java-plugin/src/main/java/com/example/tuoni/listener/TemplateListener.java`: implement the required lifecycle and `getInfo`, preserving existing presentation. Report Java listener status from resources this object actually controls; report remote native health only from received observations. Keep exec-unit generation and support declarations aligned with native implementations. For reconfiguration, follow the sibling configuration skill's validation, delivery, and rollback guidance.
- `ExecUnitListener` has no `parseResult`, but the Java listener can decode its own transport frames. Find or implement the native sender and corresponding Java receiver, read metadata using `ListenerContext`, and dispatch opaque agent requests through the `Agent` APIs. Adding native telemetry requires coordinated application framing and Java decoding; the IPC reference describes the concrete flow.

Verify factory creation, including the no-fields case, and that every exec-unit can start, exchange required data with the actual receiver, handle connection failure, and stop cleanly. Exercise supported reconfiguration. Follow the build guide to compile, rebuild affected native resources, package dependencies, and compare final JAR entries against fresh artifacts. Report platform/runtime checks that could not be completed.
