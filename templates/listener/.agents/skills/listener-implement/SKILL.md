---
name: listener-implement
description: Implement or finish an entire Tuoni listener plugin from a user's prompt by coordinating the existing configuration, logic, and output skills, then building and verifying the integrated plugin.
---

# Listener implementation

Use this skill in the listener plugin root containing `java-plugin/` and `exec-code/`. Turn the prompt into a complete implementation in the current plugin, including configuration, Java and native transport behavior, lifecycle, output, and build integration. Preserve existing work and user limits. For a request confined to one area, use the corresponding focused skill directly.

Start with [the implementation recipes](../../../docs/implementation-recipes.md): select the transport shape, fill in the small contract, and follow the minimum complete implementation in order. Direct streams, HTTP polling, relays, and external controllers have different Java/native ownership. Choose the matching shape before adapting a reference. A simple direct listener needs configuration, IPC, transport, SDK handoffs, and lifecycle; add telemetry, jobs, rotation, uploads, and live updates only when requested or required by existing behavior.

## Establish the contract

Read the plugin-root `AGENTS.md` and `CLAUDE.md` when present and follow the [context maintenance guide](../../../docs/project-context.md). Verify recorded facts against the source before using them. Work in the existing plugin; creating another scaffold is not part of this skill.

Extract the requested transport and peer roles, endpoints, inputs/defaults/validation, connection/session behavior, output surface, and reconfiguration requirements. Infer reasonable unspecified details from the prompt and existing code, and record those decisions. Ask only about missing choices that materially prevent implementation; continue independent work while awaiting answers.

Inventory `exec-code/` and reconcile it with `TemplateListener.getSupportedPayloadTypes` and `getSupportedExecUnitTypes`. Implement all existing OS/architecture implementations unless the user limits the scope. Do not drop support to avoid work.

## Apply the existing skills

Read and follow each sibling skill when its phase begins. Their linked files supply the detailed implementation instructions even when the client has not automatically discovered them; load the sections relevant to the chosen behavior. Carry the same user requirements and shared contracts through each phase; no separate user invocation is needed.

| Skill | Responsibility in the complete implementation |
| --- | --- |
| [listener-conf](../listener-conf/SKILL.md) | Implement the schema, defaults, validation, typed configuration, Java factory handoff, and delivery to every native decoder. Make the factory accept valid empty configuration when no fields are needed. Distinguish Java-only settings from native settings and define update/delivery/rollback semantics. |
| [listener-logic](../listener-logic/SKILL.md) | Implement the requested native transport, local-agent IPC helpers, Java transport counterpart, connection/session loop, start/stop/delete lifecycle, cancellation, and cleanup. Implement reconfiguration consistently with the configuration contract. |
| [listener-output](../listener-output/SKILL.md) | Implement the requested data from native senders through the actual Java receiver to the supported presentation surface. Choose a simple useful presentation when the prompt leaves it open; preserve opaque agent traffic while adding any requested telemetry. |

Define configuration, application transport, and output contracts before wiring their producers and consumers. Usually implement configuration first, behavior next, and finalize output afterward; revisit an earlier phase when integration reveals a dependency. Reuse the same typed models/codecs and preserve established field meanings and unrequested behavior. Choose UTF-8 text/JSON or explicit binary payloads appropriate to the prompt, using Java standard APIs for text/binary and a declared bundled parser for JSON. The native helper alone owns host IPC framing; follow [payload boundaries](../../../docs/execunit-ipc.md#plugin-payloads-and-host-ipc).

A focused skill may report behavior outside its scope as remaining work. Here, carry that work into the appropriate next phase whenever it is needed for the complete listener. Continue until the requested listener can be created, started, exchange data with its actual peers, expose the requested output, and stop cleanly; completing one skill does not complete this task.

## Integrate and verify

- Trace schema and validation through listener creation, both exec-unit generation paths, native configuration decoding, local-agent IPC, native-to-Java transport, Java receive/dispatch handling, output, and cleanup. Resolve remaining scaffold TODOs on that path, including helper stubs and unconditional validation failures. Prove metadata-only registration, an agent request, and a returned queued command; a bound endpoint alone is not a complete listener. Preserve explicit unsupported behavior for features outside the requested contract.
- Keep the local-agent pipe/FIFO separate from the listener's application transport. `ExecUnitListener` has no command-style `parseResult`; follow the [Java listener walkthrough](../../../docs/listener-java.md) for actual receive hooks and lifecycle ownership. Base Java resource status on owned resources and remote health on received observations. Trace supported updates through delivery and application, including rollback on failure.
- Keep Windows source lists, Linux source lists, Java dependencies, support declarations, and packaged resource names aligned with the implementation. Preserve the pipe-name placeholder and native entrypoints as required by the focused skills.
- Follow the [build guide](../../../docs/building.md) and the focused skills' relevant checks. Verify valid/invalid configuration and factory creation, startup, actual bidirectional traffic, output decoding/presentation, connection failure, shutdown/cleanup, and supported reconfiguration. Cover each in-scope implementation and confirm added output does not disrupt normal agent traffic. Consolidate overlapping checks after the integrated edits.
- Compile affected Java and native sources, rebuild native resources, package runtime dependencies, and compare the distributable JAR entries with fresh artifacts as the build guide describes. Separate compilation, packaging, and runtime evidence. An unavailable toolchain or host is an unverified check: complete independent work and report the exact gap without claiming it passed.

## Finish with maintained context

Update the plugin README's purpose, configuration examples, transport setup, and output description to match the implementation. Maintain project context throughout the workflow and before finishing, including partial work: record the implemented contracts, platform coverage, resource ownership, sender/receiver paths, checks and outcomes, artifact freshness, and concrete remaining limitations. Keep user instructions and unrelated facts intact.

Report what was implemented, how to configure/use it, the actual build/runtime checks, artifact locations, and any remaining blocker. Do not describe an unfinished requested path or an unverified runtime as complete.
