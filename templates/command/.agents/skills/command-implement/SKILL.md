---
name: command-implement
description: Implement or finish an entire Tuoni command plugin from a user's prompt by coordinating the existing configuration, logic, and output skills, then building and verifying the integrated plugin.
---

# Command implementation

Use this skill in the command plugin root containing `java-plugin/` and `exec-code/`. Turn the prompt into a complete implementation in the current plugin, including configuration, Java and native behavior, result presentation, and build integration. Preserve existing work and user limits. For a request confined to one area, use the corresponding focused skill directly.

Start with the [implementation recipe](../../../docs/implementation-recipes.md): choose the needed behavior, then follow its ordered minimum path. Its one-value trace connects a real schema/codec handoff to native senders and Java presentation with exact bytes. Treat streaming, files, jobs and live updates as conditional branches; read their detailed guides only when the prompt needs them.

**Exec-unit safety is mandatory.** The host may unload the code immediately when `Main` / `run` returns. Never crash, stop, or terminate the host process. Contain failures, and leave no invocation-owned thread, task, timer, queued work, or callback running or callable after return. Cancel, unblock, unregister, drain, and join/await before releasing shared state. Detaching a worker, marking it as background, or timing out its wait does not prove completion. When changing exec-unit code, read and apply the [host process and unload requirements](../../../docs/native-runtime.md#host-process-and-unload-requirements), including their verification checks.

## Establish the contract

Read the plugin-root `AGENTS.md` and `CLAUDE.md` when present and follow the [context maintenance guide](../../../docs/project-context.md). Verify recorded facts against the source before using them. Work in the existing plugin; creating another scaffold is not part of this skill.

Extract the requested operation, inputs/defaults/validation, returned data and presentation, execution duration, failure behavior, and any stop/update requirements. Infer reasonable unspecified details from the prompt and existing code, and record those decisions. Ask only about missing choices that materially prevent implementation; continue independent work while awaiting answers.

Inventory `exec-code/` and reconcile it with `TemplateCommandTemplate.canSendToAgent` and `TemplateCommand.supportedTypes`. Implement all existing OS/architecture implementations unless the user limits the scope. Do not drop support to avoid work.

## Apply the existing skills

Read and follow each sibling skill when its phase begins. Their linked files supply the detailed implementation instructions even when the client has not automatically discovered them; load the sections relevant to the chosen behavior. Carry the same user requirements and shared contracts through each phase; no separate user invocation is needed.

| Skill | Responsibility in the complete implementation |
| --- | --- |
| [command-conf](../command-conf/SKILL.md) | Implement the schema, defaults, validation, typed configuration, Java factory handoff, and delivery to every native decoder. Make the factory accept valid empty configuration when no fields are needed. Implement updates only when required by the command. |
| [command-logic](../command-logic/SKILL.md) | Implement the requested operation in every in-scope exec-unit, working IPC helpers, initialization, completion/failure reporting, stop handling, and cleanup. Connect the Java generation and lifecycle hooks to that behavior. |
| [command-output](../command-output/SKILL.md) | Implement all requested result data from native collection and encoding through Java parsing and presentation, including streaming or files when required. Choose a simple useful presentation when the prompt leaves it open. |

Define configuration and output contracts before wiring their producers and consumers. Usually implement configuration first, behavior next, and finalize output afterward; revisit an earlier phase when integration reveals a dependency. Reuse the same typed models and payload encoders; preserve established fields and unrequested behavior. Choose a payload representation that fits the request and available dependencies. Follow the [payload boundary](../../../docs/execunit-ipc.md#payload-boundary): Java handles inner configuration/result bytes, while the native helper and agent handle host framing.

A focused skill may report behavior outside its scope as remaining work. Here, carry that work into the appropriate next phase whenever it is needed for the complete command. Continue until the requested path works from factory creation through native execution to the user's result; completing one skill or leaving minimal output that omits requested data does not complete this task.

## Integrate and verify

- Treat the [lifecycle verification](../../../docs/native-runtime.md#required-lifecycle-verification) as a completion gate for every in-scope exec-unit. Repair unsafe worker/callback lifetimes in selected helpers, including reused code. Keep the entrypoint alive through shutdown; a terminal message or cancellation request does not make the code safe to unload.
- Trace schema and validation through command creation, both exec-unit generation paths, native configuration decoding, execution, result transport, `TemplateCommand.parseResult`, and completion. Resolve remaining scaffold TODOs on that path, including helper stubs and unconditional validation failures. Preserve explicit unsupported behavior for features outside the requested contract.
- Keep Windows source lists, Linux source lists, Java dependencies, support declarations, and packaged resource names aligned with the implementation. Preserve the pipe-name placeholder and native entrypoints as required by the focused skills.
- Follow the [build guide](../../../docs/building.md) and the focused skills' relevant checks. Verify valid/invalid configuration and factory creation, native-to-Java result compatibility, success/failure and cleanup, plus streaming/stop/updates when supported. Cover each in-scope implementation and the actual requested presentation. Consolidate overlapping checks after the integrated edits.
- Compile affected Java and native sources, rebuild native resources, package runtime dependencies, and compare the distributable JAR entries with fresh artifacts as the build guide describes. Separate compilation, packaging, and runtime evidence. An unavailable toolchain or host is an unverified check: complete independent work and report the exact gap without claiming it passed.

## Finish with maintained context

Update the plugin README's purpose, configuration examples, and output description to match the implementation. Maintain project context throughout the workflow and before finishing, including partial work: record the implemented contracts, platform coverage, lifecycle, result path, checks and outcomes, artifact freshness, and concrete remaining limitations. Keep user instructions and unrelated facts intact.

Report what was implemented, how to configure/use it, the actual build/runtime checks, artifact locations, and any remaining blocker. Do not describe an unfinished requested path or an unverified runtime as complete.
