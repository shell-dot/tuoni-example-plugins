---
name: command-implement
description: Implement or finish an entire Tuoni command plugin from a user's prompt by coordinating the existing configuration, logic, and output skills, then building and verifying the integrated plugin.
---

# Command implementation

**Windows `native-lib` requirement:** Project-authored C++ must not throw/rethrow or use exceptions for error handling. Use checked status/results and follow [the Windows exception policy](../../../docs/native-memory-safety.md#windows-no-authored-exceptions), including its distinction between authored failures and defensive dependency-exception containment.

**Native C/C++ review.** For Windows or Linux `native-lib` changes, read the [native memory-safety review](../../../docs/native-memory-safety.md) after project context and before editing C++, including configuration/output helpers. Identify buffer owners and valid lengths, check arithmetic before access, and review callback lifetimes and shared state. Investigate suspected faults in an isolated local test process; compilation or `catch (...)` is not memory-safety evidence.

Read the [exec-unit overview](../../../docs/execunit-overview.md) after project
context for a plain-language map of all three source families, their artifact
formats, and the current default lifecycle. Separate implemented behavior from
examples and TODOs; verify these starting facts against the selected plugin.

When the developer limits OSs, architectures, or exec-unit formats, follow the
[support-scope guide](../../../docs/support-scope.md). Explicit limits take
precedence over generic coverage instructions such as "all exec-units," "every
native decoder," or "both generation paths" below. Distinguish a task or test
limit from a change to the supported set, and preserve coverage on unspecified
dimensions.

The [default command](../../../README.md#default-behavior) already validates `{}`, connects managed Windows, native Windows, and Linux exec-units through their utilities, emits exact UTF-8 `DONE`, displays it in Java's `output` result, and sends checked success completion. Extend this path with the requested operation. No placeholder exception needs removing; keep updates unsupported unless requested.

Use this skill in the command plugin root containing `java-plugin/` and `exec-code/`. Turn the prompt into a complete implementation in the current plugin, including configuration, Java and native behavior, result presentation, and build integration. Preserve existing work and user limits. For a request confined to one area, use the corresponding focused skill directly.

Start with the [implementation recipe](../../../docs/implementation-recipes.md): choose the needed behavior, then follow its ordered minimum path. Its one-value trace connects a real schema/codec handoff to native senders and Java presentation with exact bytes. Treat streaming, files, jobs and live updates as conditional branches; read their detailed guides only when the prompt needs them.

**Failure cleanup is mandatory before `Main` / `start` / `run` returns.** A failed invocation must leave the host alive and safe to unload the library immediately. Implement cleanup before operation logic: give each invocation scoped ownership (RAII in C++), contain exceptions across the entire entrypoint and every worker/callback, and make cleanup nonthrowing and safe after partial startup. Every success, error, cancellation and disconnect path must stop new work, unblock owned I/O, unregister/drain callbacks, join/await all owned workers, then release resources before returning. Never terminate the host, detach work, destroy a joinable `std::thread`, or treat a sleep/join timeout as cleanup. Read the [failure-path cleanup gate](../../../docs/native-runtime.md#failure-path-cleanup-before-return) before editing native code, including reused helpers.

**Error reporting must not break cleanup.** Audit construction, connect, parsing, execution, result/error/terminal sends and cleanup itself; a trailing `close()` or one catch around the operation is insufficient. Error encoding/sending can fail: contain its exceptions, protect Linux writes against `SIGPIPE` without changing host-wide signal handlers, and finish cleanup even when reporting fails. C++ catch blocks do not catch signals or make invalid memory access safe. Before declaring the native path complete, force operation/startup/reporting failures and verify host survival, no owned work/resources left behind, and immediate compatible-host unload/repeated invocation under the [lifecycle checks](../../../docs/native-runtime.md#required-lifecycle-verification). A successful Docker build is not stability proof; record unavailable runtime checks explicitly.

**Command completion is mandatory.** Every run must reach one completion owner. On a usable connection, send exactly one checked `sendReturnSuccess` or `sendReturnFailed` before closing the reporting channel and returning, including empty success, early exits, invalid configuration, exceptions and cancellation. Output, error text, logs or a return code do not finish the command. Failure to format an error must not skip failure completion. Resolve operation-worker failures and drain result writes before success; never silently return or send both outcomes. Apply the [command completion gate](../../../docs/command-completion.md), including actual host terminal-state tests and observable failure handling when the channel cannot deliver.

**Full Docker build is mandatory.** Unless the user explicitly overrides the build requirement or route, run `make build` from this plugin's root in a Linux/WSL shell after substantial coherent steps and after the final code/build-input change. This applies to focused configuration, logic, and output changes too. Build every in-scope exec-unit, perform required conversion, and compile/package/export the Java plugin. Actually execute the command, wait for completion, and verify its artifacts using the [full-build gate](../../../docs/building.md#required-build-checkpoints). Partial targets, a Java-only compile, or a planned command do not satisfy this requirement. Fix build errors and rerun the full pipeline. If Docker is missing or unusable, inform the user and report builds blocked; no automatic local fallback.

**Java artifact and initialization gate.** Check actual SDK signatures and dependency ownership before Java edits. Bundle every plugin-owned runtime dependency and its transitives in the exported distributable; `implementation` alone and server-provided Jackson are insufficient. Keep SDK/verified host contracts separate. Follow [Java verification](../../../docs/java-verification.md): run the copied archive checker against the exact exported JAR (including `--jackson3` when used), then run an isolated Docker startup/factory smoke test using that JAR and the verified loader boundary. Exercise providers, initialization, metadata/schema/examples and valid/invalid factory paths; never use Gradle's normal runtime classpath to hide missing dependencies. Record the JAR path/hash and results. Failed or untested initialization cannot be reported as working merely because the full build passed.

**Configuration and response agreement.** Apply the [byte-verification gate](../../../docs/payload-verification.md): compare actual Java configuration bytes with every native decoder, then separately verify those same bytes through the real IPC framing/unwrapping path. Normalize outgoing SDK configuration buffers to position zero and exact payload length. Feed actual native responses into the real Java receiver/parser. Preserve the payload/host-envelope boundary and retain regression fixtures for frame errors.

## Establish the contract

Read the plugin-root `AGENTS.md` and `CLAUDE.md` when present and follow the [context maintenance guide](../../../docs/project-context.md). Verify recorded facts against the source before using them. Work in the existing plugin; creating another scaffold is not part of this skill.

Extract the requested operation, inputs/defaults/validation, returned data and presentation, execution duration, failure behavior, and any stop/update requirements. Infer reasonable unspecified details from the prompt and existing code, and record those decisions. Ask only about missing choices that materially prevent implementation; continue independent work while awaiting answers.

Inventory `exec-code/` and reconcile it with `TemplateCommandTemplate.canSendToAgent` and `TemplateCommand.supportedTypes`. Cover the existing OS/architecture/format combinations within the user's requested scope. Do not drop support merely to avoid requested work; explicit support restrictions still apply.

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

- Apply the [completion tests](../../../docs/command-completion.md#required-completion-tests): every usable-channel case has exactly one appropriate terminal message, including empty output, early failures and cancellation; verify the host reaches its expected final state. A result/error payload or a successful build alone is insufficient.
- Complete both levels of the [configuration/response byte checks](../../../docs/payload-verification.md), including both Java generation paths, actual native connection helpers, and the real Java response receiver. Rebuild all in-scope native artifacts and the distributable after the last code/build-input change, then verify its resource bytes against those outputs. Keep payload-codec, framed-transport, compilation, and packaging results separate.
- Treat the [lifecycle verification](../../../docs/native-runtime.md#required-lifecycle-verification) as a completion gate for every in-scope exec-unit. Implement the failure-cleanup owner before operation logic, audit every return/throw/reporting path, and repair unsafe worker/callback lifetimes in selected helpers, including reused code. Force a failed operation plus a failed error send; verify cleanup before immediate unload and another invocation. Keep the entrypoint alive through shutdown; a terminal message or cancellation request does not make the code safe to unload.
- Trace schema and validation through command creation, both exec-unit generation paths, native configuration decoding, execution, result transport, `TemplateCommand.parseResult`, and completion. Extend the implemented no-op hooks and resolve TODOs required by the requested operation. The default validation, utilities, and result/completion path already work at source level; retain their contracts. Preserve explicit unsupported behavior for features outside the requested contract.
- Keep managed Windows sources in the `.csproj`, Windows native sources in `exec-code/win-native/build_windows.sh`, and Linux sources in `exec-code/linux/build_linux.sh` aligned with Java dependencies, support declarations, and packaged resource names. Windows native x86/x64 DLLs export `start`; Linux exports `run`. Preserve the pipe-name placeholder and native entrypoints as required by the focused skills.
- Follow the [build guide](../../../docs/building.md) and the focused skills' relevant checks. Verify valid/invalid configuration and factory creation, native-to-Java result compatibility, success/failure and cleanup, plus streaming/stop/updates when supported. Cover each in-scope implementation and the actual requested presentation. Consolidate overlapping checks after the integrated edits.
- Execute the complete Docker `make build`, wait for its exit status, and compare the distributable JAR entries with that build's exported native artifacts as the build guide describes. Record the command, working directory, exit status and artifact paths. Separate compilation, packaging, and runtime evidence. An unavailable toolchain or host is an unverified check: complete independent work and report the exact gap without claiming it passed.

## Finish with maintained context

Update the plugin README's purpose, configuration examples, and output description to match the implementation. Maintain project context throughout the workflow and before finishing, including partial work: record the implemented contracts, platform coverage, lifecycle, result path, checks and outcomes, artifact freshness, and concrete remaining limitations. Keep user instructions and unrelated facts intact.

Report what was implemented, how to configure/use it, the actual build/runtime checks, artifact locations, and any remaining blocker. Do not describe an unfinished requested path or an unverified runtime as complete.
