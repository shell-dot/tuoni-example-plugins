---
name: new-command
description: Create a named Tuoni command plugin from this repository's template and continue with command-implement when the user describes the requested behavior.
---

# New command plugin

For Windows `native-lib` work, carry the hard [no authored exceptions requirement](../../../templates/command/docs/native-memory-safety.md#windows-no-authored-exceptions) into the local skill, including older copies: no project-authored throw/rethrow or exception-based error handling; require checked status/results.

When continuing into C++ implementation, pass the [native memory-safety review](../../../templates/command/docs/native-memory-safety.md), copied as `docs/native-memory-safety.md`, to the local skill. It covers general Windows/Linux library ownership, bounds, API failures, concurrency, and isolated diagnostic tests; creating a scaffold provides no runtime safety evidence.

The [exec-unit overview](../../../templates/command/docs/execunit-overview.md)
explains the source template's three implementations, generated formats, and
existing default behavior. It is copied as `docs/execunit-overview.md`; use the
generated plugin's local copy and source when describing that project's state.

If the developer requests only certain OSs, architectures, or exec-unit formats,
use the [support-scope guide](../../../templates/command/docs/support-scope.md),
copied as `docs/support-scope.md`. Carry the selected combinations and the
distinction between task limits and support restrictions into the local skills.
The copied source inventory does not override an explicit support limit.

Find the repository containing this skill: resolve `../../..` from the skill directory `.agents/skills/new-command/` (or its `.claude` mirror) and confirm `templates/command/` and `tools/scaffold_plugin.py` exist. This is the helper's repository, which may differ from the user's current directory. Use the requested command name, or infer one from the user's description or destination folder. If no name can be inferred, use `new-command`.

Keep the user's original working directory while invoking the helper by its absolute path. Use Python 3.9+ (`python --version` or `python3 --version`). Without a requested folder, replace the placeholders and run:

```text
python3 "<repo-root>/tools/scaffold_plugin.py" command --name "<name>"
```

With an exact requested destination:

```text
python3 "<repo-root>/tools/scaffold_plugin.py" command --name "<name>" --folder "<destination>"
```

For an explicit support restriction, add `--execunits "native-lib dotnet-dll"`
and/or `--os "windows linux"` to the same helper call before creating the
plugin. Formats are `shellcode-native`, `dotnet-dll`, `dotnet-exe`, and
`native-lib`; operating systems are `windows` and `linux`. Space- or
comma-separated values are accepted. Pass only requested support restrictions,
not task-only or test-only limits. The helper selects existing combinations and
rejects an OS with no compatible format. Check the generated support table and
Java declarations before continuing. For an architecture restriction, which the
helper does not accept, narrow the generated declarations and context explicitly
before treating the scaffold as complete.

Use `python` instead of `python3` where that is the Python 3 command. For example, from any PowerShell working directory: `python "C:/Work/dev_examples/tuoni-example-plugins/tools/scaffold_plugin.py" command --name "Bob" --folder "C:/Work/Bob"` (replace the repository path with the located one).

Without `--folder`, the destination is `<repo-root>/workspace/commands/<normalized-name>`, regardless of the user's current directory. For example, the name `Daily Check` becomes `workspace/commands/daily-check` under this repository. The helper creates missing parent directories and reuses existing `workspace/` and `commands/` directories. An explicit `--folder` overrides this default: a relative path is relative to the user's original directory, and an absolute path is used directly. The helper refuses any existing plugin destination and omits generated build outputs. If the plugin destination exists, report that conflict and preserve it; do not delete it or silently choose a different folder. Only after successful creation, use the returned destination as the root for all implementation, validation, and build work.

The helper preserves the normalized command/listener name while prefixing Java package components that start with digits or are reserved words. Use the generated identifiers and paths rather than reconstructing them from the display name.

The helper keeps these renamed locations in sync:

- `java-plugin/src/main/java/`: package and source directory; `TemplateCommand`, `TemplateCommandTemplate`, `TemplateCommandPlugin`, and `TemplateConfigurationSchema` class names, filenames, references, and `TemplateCommandTemplate.NAME`.
- `java-plugin/src/main/resources/META-INF/services/`: provider class name. Keep the SDK interface filename.
- `java-plugin/settings.gradle.kts` and `build.gradle.kts`: project name, group, `Plugin-Id`, display name, description, and Linux resource filename.
- `exec-code/win/`: solution and project filenames, solution project name and GUID, C# namespace, `RootNamespace`, `AssemblyName`, and post-build Windows shellcode resource path.
- `exec-code/linux/`: command source folder, compiler input, and output library name. Keep the exported `run` function.
- `TemplateCommand` resource constants, `scripts/docker/Dockerfile`, `Makefile`, and copied `README.md`: Windows shellcode, Linux library, JAR, executable, and build paths.

Keep `QQQWWWEEE` as the Windows pipe-name placeholder. The helper preserves the command's working default: `{}` validation, zero-byte native configuration, pipe/FIFO startup, exact UTF-8 `DONE` output, Java presentation in `output`, and checked success completion. The generic `ShellcodeResource` utility name and extension comments remain intact. After creation, read the copied `AGENTS.md` and `CLAUDE.md` before further edits or validation; follow their context links.

Use the [current command default](../../../templates/command/README.md#default-behavior) as the starting contract. Adding requested behavior extends this default; it does not require replacing the implemented utility classes. Compile/build evidence and host runtime evidence remain separate.

Check generated identifiers against the requested name and check referenced paths. A requested name containing "Template" is legitimate; do not treat every occurrence as stale. Verify that the `command-implement`, `command-conf`, `command-logic`, and `command-output` skills were copied under the destination's `.agents` and `.claude` skill trees and their links resolve to the copied `docs/` files.

After scaffolding, route the original request:

- If the user describes what the command should do, continue immediately with the generated plugin's `.agents/skills/command-implement/SKILL.md` (or its `.claude/skills/command-implement/SKILL.md` mirror). Read and follow that skill even if automatic discovery has not refreshed. A behavior description is enough; no separate invocation, explicit word "implement", or additional confirmation is needed. Relay the complete original behavior request, inputs, outputs, configuration, failure/stop expectations, platform limits, and other constraints. Record those as requested requirements in the generated project context before implementation, and preserve unresolved choices for the implementation skill. Work in the returned destination and carry the request through implementation, builds, and verification under that skill.
- If the prompt gives only a name/location, or explicitly asks for a scaffold only, preserve the implemented `DONE` default and its extension hooks. Explicit scaffold-only instructions take precedence even when a future behavior is described. Unless the user asks to skip builds, execute the complete `make build` from the generated plugin root, wait for its result, and verify the exported exec-units and packaged Java plugin. Use Docker unless the user explicitly requests another route. If Docker is missing or unusable, inform the user and mark builds blocked; do not fall back to local tools. Follow the [build checkpoints](../../../templates/command/docs/building.md#required-build-checkpoints), also copied to `docs/building.md`. Report compile, conversion, packaging and unavailable phases separately; scaffold builds do not prove implemented behavior.

For behavior implementation, explicitly relay the [command completion gate](../../../templates/command/docs/command-completion.md), copied to `docs/command-completion.md`, to `command-implement`. Every invocation needs one finalizer and, on a usable connection, a checked terminal success/failure report before the connection closes and `run` returns. This includes zero output, early returns, invalid configuration, exceptions and cancellation. Error text is not failure completion. Require wire/host terminal-state tests and an observable host failure path for startup/disconnect cases; never call a silently unfinished command implemented.

For behavior implementation, require the [Java artifact and initialization gate](../../../templates/command/docs/java-verification.md), copied to `docs/java-verification.md`, in `command-implement`. Check actual SDK signatures; bundle plugin-owned dependencies and their transitives in the exact Docker-exported JAR. Run `scripts/verify_java_artifact.py` for that JAR, with `--jackson3` when used, then a separate isolated Docker startup/factory smoke test. Do not rely on server Jackson or Gradle's normal runtime classpath, and do not equate compilation with initialization. Preserve the JAR path/hash and test outcomes in project context.

For behavior implementation, make [failure-path cleanup](../../../templates/command/docs/native-runtime.md#failure-path-cleanup-before-return), copied as `docs/native-runtime.md`, the first native implementation step. Relay this explicitly to `command-implement`: Linux `run` must contain startup, operation, worker and reporting failures, stop/unblock/drain/join all owned work, and release resources before returning even when error delivery fails. Use per-invocation RAII ownership and nonthrowing cleanup; a final `close()`, sleep, detached worker or successful build is insufficient. Audit reused helpers and force failing-operation, partial-startup and broken-error-channel cases, then verify host survival and immediate compatible-loader unload/repeated invocation. Report any unavailable runtime checks; do not call the exec-unit stable on compilation evidence alone.

When the prompt describes behavior, `command-implement` must actually execute the complete Docker `make build` from the generated plugin root after substantial coherent steps and after the final code/build-input change. Wait for completion, fix build errors and rerun the full pipeline, then verify every in-scope native export and the packaged Java plugin. Record the command, working directory, exit status and artifact paths. Scaffolding, source edits, partial compile targets or a proposed build command are not completion. Use another route only when explicitly requested by the user. If Docker is missing or unusable, inform the user and report the blocked build without a local fallback. Require the [configuration and response byte checks](../../../templates/command/docs/payload-verification.md), available in the new plugin as `docs/payload-verification.md`: normalize outgoing SDK buffers to position zero/exact length, compare actual encoder/decoder bytes, then verify the real framing/unwrapping and response paths. Respect explicit user overrides and report unverified checks.

When implementing Java/exec-unit data exchange, choose and document a payload format suited to the requested data, such as UTF-8 text, JSON, or explicitly laid-out binary fields. Match Java encoding/decoding to every native implementation. Use Java's standard text/binary APIs, or declare and bundle a parser dependency when needed. Keep the native helpers responsible for the separate [host IPC framing](../../../templates/command/docs/execunit-ipc.md); the Java SDK hands the plugin the inner payload bytes. No external server checkout is needed to define or encode that payload.

Before finishing, read the generated plugin's `AGENTS.md` and `CLAUDE.md` and refresh its shared context using the [context maintenance guide](../../../templates/command/docs/project-context.md), also copied as `docs/project-context.md`. The helper copies and renames the starter context files. Record the actual name, purpose requested by the user, platform scope, source paths, the implemented default and remaining extension work, and commands/checks performed, including native artifact freshness and unavailable checks. Create missing context files according to that guide; preserve existing instructions. Do not carry successful template-repository checks into a generated plugin as if they were run there.

Report the created path, whether behavior was implemented or only scaffolded, the context file updated, and actual compilation, packaging, runtime checks, and remaining limitations. Do not stop at reporting scaffold creation when the user also requested behavior.
