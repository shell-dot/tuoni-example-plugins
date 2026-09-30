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

1. **Identity, purpose, and user scope.** Record the actual plugin name/ID, implemented purpose, and relevant user limits such as selected OSs. Separate requested behavior from completed behavior.
2. **Source map.** List the real Java package/classes, native entrypoints, helper files, and build source lists for every existing exec-unit. Reconcile source implementations with advertised support; record remaining discrepancies.
3. **Configuration and protocol.** Record the actual schema location, typed configuration classes, meaningful defaults/validation, startup serialization/decoding points, and implemented payload fields, encoding, boundaries, and versioning. Describe update support and patch/full-replacement semantics when established. Link larger protocol tables rather than duplicating them.
4. **Runtime and lifecycle.** Record the real initialization/behavior/cleanup points, connection ownership, cancellation mechanism, resource lifetime, and supported live-update path. For each owned worker/task/callback, record its owner, stop/unblock mechanism, and join/drain point before entrypoint return. Record actual host-survival and unload checks, plus unresolved lifetime risks, using the [lifecycle requirements](native-runtime.md#host-process-and-unload-requirements). Distinguish Java-side state from observed native state.
5. **Output.** Record native encoding, the Java receive/parser method, result fields/format, streaming/final behavior, and the actual presentation surface.
6. **Builds and verification.** Record reproducible commands relative to the plugin root and their outcomes. Distinguish source compilation, native artifact generation, JAR packaging, and runtime checks. Note the platform/toolchain and whether bundled native artifacts were rebuilt and compared with this change; call out stale or unverified artifacts.
7. **Remaining work.** Record concrete TODOs, incomplete platform coverage, failed/unavailable checks, and the next useful step. Remove or revise entries that the current work actually resolved.

A short fact plus a relative file link is usually enough. Use repository-relative paths, not absolute workstation paths or temporary test-directory names. Do not copy secrets, private credentials, raw user transcripts, or lengthy tool logs into these files.

## This template's starting source map

The following are navigation hints for the unrenamed template. After scaffolding, record the generated names and paths that actually exist; after later refactors, replace stale entries. Artifact paths identify expected build outputs; if an output is absent, record it as not generated.

| Area | Current template files / methods |
| --- | --- |
| Java registration and factory | `java-plugin/src/main/java/com/example/tuoni/listener/TemplateListenerPlugin.java`: schema, validation, `create`. |
| Java lifecycle/configuration/output | Same package: `TemplateListener.java`: constructor, `start`, `stop`, `delete`, `reconfigure`, `generateExecUnit`, `generateShellCode`, `serializeUpdatedConfiguration`, `getInfo`, support declarations; `TemplateConfigurationSchema.java`; `ShellcodeResource.java`. |
| Windows | `exec-code/win/Program.cs`: `Initialize`, `WaitForStop`, `Cleanup`; `exec-code/win/exec-unit-utils/`; `exec-code/win/listener-execunit.csproj` and `listener-execunit.sln`. |
| Linux | `exec-code/linux/listener/Main.cpp`: exported `run`; `exec-code/linux/common/`; `exec-code/linux/build_linux.sh` explicit source list. |
| Packaging | `java-plugin/build.gradle.kts`, `Makefile`, `scripts/docker/Dockerfile`; `java-plugin/src/main/resources/listener.shellcode`; `exec-code/linux/build/listener-linux.native64_so`. |

When listener transport code is implemented, add its actual native sender and Java receiver files to the source map. The template does not already contain a complete transport or a command-style `parseResult` method.

For a fresh scaffold, schema/behavior/helper TODOs are unfinished work. The worked fields, example payloads, and decoder snippets in `docs/configuration.md` are reference examples until implemented in source. Likewise, instructions in `docs/native-runtime.md`, `docs/execunit-ipc.md`, and `docs/building.md` are not proof that behavior exists or a build passed.

## Update after each skill

Make the context update before the skill's final report, using the files actually changed and checks actually run. Update context for partial work too: describe the completed portion, the blocker or limitation, and what remains. Do not report a proposed feature, unexecuted command, or copied example as completed work.

| Skill | Context to create or refresh |
| --- | --- |
| Scaffolding (`new-listener`) | Actual name/ID/package, generated destination-relative source map, copied skills/docs, advertised and existing exec-units, untouched TODOs, and the exact scaffold/build checks completed. |
| Complete implementation (`listener-implement`) | User-requested scope and inferred decisions; integrated configuration, transport/lifecycle, and output contracts; platform coverage; build/runtime evidence and artifact freshness; any remaining work across the focused skills. |
| Configuration (`listener-conf`) | Actual schema/typed classes, added or changed fields/defaults/validation, Java handoff methods, each native decoder, payload fields/encoding/versioning, update behavior, and cross-language checks performed. |
| Logic (`listener-logic`) | Implemented behavior and limits, touched exec-units, entrypoints/helpers, lifecycle/cancellation/update handling, the output contract retained or added, and actual build/runtime results. |
| Output (`listener-output`) | Requested output that was implemented, native payload/transport, Java decoder and presentation, streaming/final semantics, protocol compatibility decisions, and checks performed on each affected exec-unit. |

When only documentation or one platform changes, say that directly and preserve the recorded state of other implementations. An absent toolchain is an unverified check, not a failed implementation or a successful build.

Before finishing, verify that new facts match source, referenced files exist, pointers resolve without a cycle, and shared facts agree if both root files hold context. Preserve user rules, unrelated sections, and useful history of unresolved limitations. Keep the final response's completion/test claims consistent with the context files.
