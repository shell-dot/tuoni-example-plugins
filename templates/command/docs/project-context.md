# Maintaining project context

Use this guide after scaffolding or changing this plugin's configuration, behavior, or output. The root context files give later work the actual project state. Keep this guide as reference instructions; record implementation facts in the plugin's own context files.

## Read before editing

Read all applicable `AGENTS.md` and `CLAUDE.md` instructions, including the plugin-root files and any applicable directory instructions, before editing code or context. Follow links that identify the project's context source. Preserve user instructions and existing sections unrelated to the task. A context update does not authorize changing those instructions.

## Choose the context location

Fresh copies of this template use `AGENTS.md` for shared project facts and a short `CLAUDE.md` instruction linking to it. For older plugins, preserve the existing organization:

| Existing state | Update |
| --- | --- |
| Neither root file exists | Create `AGENTS.md` with the verified project facts; create `CLAUDE.md` directing readers to `AGENTS.md`. |
| Only one root file exists | Keep that file as the context source, preserving its instructions; add the missing peer as a short pointer to it. |
| One file points to a substantive peer | Update the substantive file; retain the pointer and any separate instructions. |
| Both files contain substantive content | Update the existing relevant sections and keep overlapping project facts consistent. Preserve file-specific instructions and organization. |

Use a direct relative link in a root pointer: its target is `AGENTS.md` for this template's [shared context](../AGENTS.md). Tell readers to read that file before making changes. Reverse the target when `CLAUDE.md` is the established source. Never make the files point to each other without a substantive context source. Repair a broken pointer by locating the intended source or creating one of the two files as the factual source, while preserving existing instructions.

If a file primarily contains agent instructions, add a clearly separated project-context section instead of replacing its contents. Do not force existing detailed context into a new layout just to match the outline below.

## Keep these facts concise and current

Use the existing headings where possible; create only sections that help the next task.

1. **Identity, purpose, and user scope.** Record the actual plugin name/ID, implemented purpose, and relevant user limits. For selected OSs, architectures, or exec-unit formats, use the [support-scope guide](support-scope.md): record exact combinations, distinguish task/test limits from support restrictions, and separate requested, advertised, implemented, and verified coverage. Separate requested behavior from completed behavior.
2. **Source map.** List the real Java package/classes, native entrypoints, helper files, and build source lists for every existing exec-unit. Reconcile source implementations with advertised support; record remaining discrepancies.
3. **Configuration and protocol.** Record the actual schema location, typed configuration classes, meaningful defaults/validation, startup serialization/decoding points, and implemented payload format, field layout and any versioning. Describe update support and patch/full-replacement semantics when established. Link larger protocol tables rather than duplicating them. Link reusable Java/native fixtures and record both payload equality/typed-value checks and real framing/unwrapping checks from [payload verification](payload-verification.md); distinguish unavailable host checks.
4. **Runtime and lifecycle.** Record the real initialization/behavior/cleanup points, connection ownership, cancellation mechanism, resource lifetime, and supported live-update path. For each owned worker/task/callback, record its owner, stop/unblock mechanism, and join/drain point before entrypoint return. Record the [failure-path audit](native-runtime.md#failure-path-cleanup-before-return): ownership and cleanup for partial initialization, every early return/throw, and failed result/error reporting. Link regression fixtures for forced operation/startup/reporting failures, and record actual host-survival, immediate unload and repeated-invocation checks plus unresolved lifetime risks using the [lifecycle requirements](native-runtime.md#host-process-and-unload-requirements). Distinguish Java-side state from observed native state.
5. **Output.** Record native encoding, the Java receive/parser method, result fields/format, streaming/final behavior, and the actual presentation surface. Record the [completion owner](command-completion.md), checked terminal-write contract, outcome for stop/cancel, actual wire/host final-state observations and any startup/transport failure fallback gaps. Separate a terminal frame received by the host from result text or a helper merely being called.
6. **Builds and verification.** Record the executed full Docker build command, plugin working directory, exit status and exported artifact paths, along with reproducible commands for other checks and their outcomes. Distinguish source compilation, native artifact generation, JAR packaging, and runtime checks. Note the platform/toolchain and whether bundled native artifacts were rebuilt and compared with this change; call out stale or unverified artifacts. Record milestone/final build results, Docker readiness/blockers and any explicit user override allowing a non-Docker route, and explicit user build skips under the [build checkpoints](building.md#required-build-checkpoints). Record Java dependency ownership and exact versions, the distributed JAR path/hash, archive-check and isolated startup/factory results under the [Java verification gate](java-verification.md). Note the loader/SDK used and any skipped or failed initialization paths separately from compilation.
7. **Remaining work.** Record concrete TODOs, incomplete platform coverage, failed/unavailable checks, and the next useful step. Remove or revise entries that the current work actually resolved.

A short fact plus a relative file link is usually enough. Use repository-relative paths, not absolute workstation paths or temporary test-directory names. Do not copy secrets, private credentials, raw user transcripts, or lengthy tool logs into these files.

Use the [default behavior](../README.md#default-behavior) when recording a fresh copy. Track requested extensions separately from existing boilerplate, and preserve intentional TODOs outside the user's scope. Source-template checks remain distinct from generated-instance builds and runtime checks.

## This template's starting source map

The following are navigation hints for the unrenamed template. After scaffolding, record the generated names and paths that actually exist; after later refactors, replace stale entries. Artifact paths identify expected build outputs; if an output is absent, record it as not generated.

| Area | Current template files / methods |
| --- | --- |
| Java registration and factory | `java-plugin/src/main/java/com/example/tuoni/command/TemplateCommandPlugin.java`; `TemplateCommandTemplate.java`: schema, validation, examples, `createCommand`, supported agents/types. |
| Java execution/configuration/output | Same package: `TemplateCommand.java`: constructor, `generateExecUnit`, `generateShellCode`, `serializeCommandUpdate`, `parseResult`, `forceStop`; `TemplateConfigurationSchema.java`; `ShellcodeResource.java`. |
| Managed Windows | `exec-code/win/Program.cs`: `Initialize`, `Execute`, `Complete`, `Cleanup`; `exec-code/win/exec-unit-utils/`; `exec-code/win/command-execunit.csproj` and `command-execunit.sln`. |
| Windows native | `exec-code/win-native/command/Main.cpp`: exported `start`, scoped connection and terminal report; `exec-code/win-native/exec-unit-utils/`; `exec-code/win-native/build_windows.sh` explicit source list and `exports.def`. |
| Linux | `exec-code/linux/command/Main.cpp`: exported `run`; `exec-code/linux/common/`; `exec-code/linux/build_linux.sh` explicit source list. |
| Packaging | `java-plugin/build.gradle.kts`, `Makefile`, `scripts/docker/Dockerfile`; `java-plugin/src/main/resources/command.shellcode`; `exec-code/win/bin/Release/dotnet-exe/` and `dotnet-dll/` managed artifacts/method sidecar; `exec-code/win-native/build/command.native32_dll` and `command.native64_dll`; `exec-code/linux/build/command-linux.native64_so`. |

The fresh command scaffold implements a no-op with empty-object validation, `DONE` text output, checked result/completion sends, and scoped cleanup. Describe added behavior and new resources separately; the defaults still need platform/host verification after generation. The worked fields, example payloads, and decoder snippets in `docs/configuration.md` are reference examples until implemented in source. Likewise, instructions in `docs/native-runtime.md`, `docs/execunit-ipc.md`, and `docs/building.md` are not proof that behavior exists or a build passed.

## Update after each skill

Make the context update before the skill's final report, using the files actually changed and checks actually run. Update context for partial work too: describe the completed portion, the blocker or limitation, and what remains. Do not report a proposed feature, unexecuted command, or copied example as completed work.

| Skill | Context to create or refresh |
| --- | --- |
| Scaffolding (`new-command`) | Actual name/ID/package, generated destination-relative source map, copied skills/docs, advertised and existing exec-units, the implemented `DONE` default, and the exact scaffold/build checks completed. |
| Complete implementation (`command-implement`) | User-requested scope and inferred decisions; integrated configuration, behavior, and output contracts; platform coverage; build/runtime evidence and artifact freshness; any remaining work across the focused skills. |
| Configuration (`command-conf`) | Actual schema/typed classes, added or changed fields/defaults/validation, Java handoff methods, each native decoder, payload format and any versioning, update behavior, and cross-language checks performed. |
| Logic (`command-logic`) | Implemented behavior and limits, touched exec-units, entrypoints/helpers, lifecycle/cancellation/update handling, the output contract retained or added, and actual build/runtime results. |
| Output (`command-output`) | Requested output that was implemented, native payload/transport, Java decoder and presentation, streaming/final semantics, protocol compatibility decisions, and checks performed on each affected exec-unit. |

When only documentation or one platform changes, say that directly and preserve the recorded state of other implementations. An absent toolchain is an unverified check, not a failed implementation or a successful build.

Before finishing, verify that new facts match source, referenced files exist, pointers resolve without a cycle, and shared facts agree if both root files hold context. Preserve user rules, unrelated sections, and useful history of unresolved limitations. Keep the final response's completion/test claims consistent with the context files.
