---
name: new-listener
description: Create a named Tuoni listener plugin from this repository's template and continue with listener-implement when the user describes the requested behavior.
---

# New listener plugin

Find the repository containing this skill: resolve `../../..` from the skill directory `.agents/skills/new-listener/` (or its `.claude` mirror) and confirm `templates/listener/` and `tools/scaffold_plugin.py` exist. This is the helper's repository, which may differ from the user's current directory. Use the requested listener name, or infer one from the user's description or destination folder. If no name can be inferred, use `new-listener`.

Keep the user's original working directory while invoking the helper by its absolute path. Use Python 3.9+ (`python --version` or `python3 --version`). Without a requested folder, replace the placeholders and run:

```text
python3 "<repo-root>/tools/scaffold_plugin.py" listener --name "<name>"
```

With an exact requested destination:

```text
python3 "<repo-root>/tools/scaffold_plugin.py" listener --name "<name>" --folder "<destination>"
```

Use `python` instead of `python3` where that is the Python 3 command. For example, from any PowerShell working directory: `python "C:/Work/dev_examples/tuoni-example-plugins/tools/scaffold_plugin.py" listener --name "Beacon" --folder "C:/Work/Beacon"` (replace the repository path with the located one).

Without `--folder`, the destination is `<repo-root>/workspace/listeners/<normalized-name>`, regardless of the user's current directory. For example, the name `Daily Check` becomes `workspace/listeners/daily-check` under this repository. The helper creates missing parent directories and reuses existing `workspace/` and `listeners/` directories. An explicit `--folder` overrides this default: a relative path is relative to the user's original directory, and an absolute path is used directly. The helper refuses any existing plugin destination and omits generated build outputs. If the plugin destination exists, report that conflict and preserve it; do not delete it or silently choose a different folder. Only after successful creation, use the returned destination as the root for all implementation, validation, and build work.

The helper preserves the normalized command/listener name while prefixing Java package components that start with digits or are reserved words. Use the generated identifiers and paths rather than reconstructing them from the display name.

The helper keeps these renamed locations in sync:

- `java-plugin/src/main/java/`: package and source directory; `TemplateListener`, `TemplateListenerPlugin`, and `TemplateConfigurationSchema` class names, filenames, and references.
- `java-plugin/src/main/resources/META-INF/services/`: provider class name. Keep the SDK interface filename.
- `java-plugin/settings.gradle.kts` and `build.gradle.kts`: project name, group, `Plugin-Id`, display name, description, and Linux resource filename.
- `exec-code/win/`: solution and project filenames, solution project name and GUID, C# namespace, `RootNamespace`, `AssemblyName`, and post-build Windows shellcode resource path.
- `exec-code/linux/`: listener source folder, compiler input, and output library name. Keep the exported `run` function.
- `TemplateListener` resource constants, `scripts/docker/Dockerfile`, `Makefile`, and copied `README.md`: Windows shellcode, Linux library, JAR, executable, and build paths.

Keep `QQQWWWEEE` as the Windows pipe-name placeholder. The helper leaves behavior TODOs and the generic `ShellcodeResource` utility name intact. After creation, read the copied `AGENTS.md` and `CLAUDE.md` before further edits or validation; follow their context links.

Check generated identifiers against the requested name and check referenced paths. A requested name containing "Template" is legitimate; do not treat every occurrence as stale. Verify that the `listener-implement`, `listener-conf`, `listener-logic`, and `listener-output` skills were copied under the destination's `.agents` and `.claude` skill trees and their links resolve to the copied `docs/` files.

After scaffolding, route the original request:

- If the user describes what the listener should do, continue immediately with the generated plugin's `.agents/skills/listener-implement/SKILL.md` (or its `.claude/skills/listener-implement/SKILL.md` mirror). Read and follow that skill even if automatic discovery has not refreshed. A behavior description is enough; no separate invocation, explicit word "implement", or additional confirmation is needed. Relay the complete original behavior request, inputs, outputs, configuration, failure/stop expectations, platform limits, and other constraints. Record those as requested requirements in the generated project context before implementation, and preserve unresolved choices for the implementation skill. Work in the returned destination and carry the request through implementation, builds, and verification under that skill.
- If the prompt gives only a name/location, or explicitly asks for a scaffold only, leave the behavior TODOs in place. Explicit scaffold-only instructions take precedence even when a future behavior is described. Unless the user asks to skip builds, execute the complete `make build` from the generated plugin root, wait for its result, and verify the exported exec-units and packaged Java plugin. Use Docker unless the user explicitly requests another route. If Docker is missing or unusable, inform the user and mark builds blocked; do not fall back to local tools. Follow the [build checkpoints](../../../templates/listener/docs/building.md#required-build-checkpoints), also copied to `docs/building.md`. Report compile, conversion, packaging and unavailable phases separately; scaffold builds do not prove implemented behavior.

For behavior implementation, require the [Java artifact and initialization gate](../../../templates/listener/docs/java-verification.md), copied to `docs/java-verification.md`, in `listener-implement`. Check actual SDK signatures; bundle plugin-owned dependencies and their transitives in the exact Docker-exported JAR. Run `scripts/verify_java_artifact.py` for that JAR, with `--jackson3` when used, then a separate isolated Docker startup/factory smoke test. Do not rely on server Jackson or Gradle's normal runtime classpath, and do not equate compilation with initialization. Preserve the JAR path/hash and test outcomes in project context.

For behavior implementation, make [failure-path cleanup](../../../templates/listener/docs/native-runtime.md#failure-path-cleanup-before-return), copied as `docs/native-runtime.md`, the first native implementation step. Relay this explicitly to `listener-implement`: Linux `run` must contain startup, operation, worker and reporting failures, stop/unblock/drain/join all owned work, and release resources before returning even when error delivery fails. Use per-invocation RAII ownership and nonthrowing cleanup; a final `close()`, sleep, detached worker or successful build is insufficient. Audit reused helpers and force failing-operation, partial-startup and broken-error-channel cases, then verify host survival and immediate compatible-loader unload/repeated invocation. Report any unavailable runtime checks; do not call the exec-unit stable on compilation evidence alone.

When the prompt describes behavior, `listener-implement` must actually execute the complete Docker `make build` from the generated plugin root after substantial coherent steps and after the final code/build-input change. Wait for completion, fix build errors and rerun the full pipeline, then verify every in-scope native export and the packaged Java plugin. Record the command, working directory, exit status and artifact paths. Scaffolding, source edits, partial compile targets or a proposed build command are not completion. Use another route only when explicitly requested by the user. If Docker is missing or unusable, inform the user and report the blocked build without a local fallback. Require the [configuration and response byte checks](../../../templates/listener/docs/payload-verification.md), available in the new plugin as `docs/payload-verification.md`: normalize outgoing SDK buffers to position zero/exact length, compare actual encoder/decoder bytes, then verify the real framing/unwrapping and response paths. Respect explicit user overrides and report unverified checks.

When implementing Java/exec-unit data exchange, choose and document a payload format suited to the requested data, such as UTF-8 text, JSON, or explicitly laid-out binary fields. Match Java encoding/decoding to every native implementation. Use Java's standard text/binary APIs, or declare and bundle a parser dependency when needed. Keep the native helpers responsible for the separate [host IPC framing](../../../templates/listener/docs/execunit-ipc.md); the Java SDK hands the plugin the inner payload bytes. No external server checkout is needed to define or encode that payload.

Before finishing, read the generated plugin's `AGENTS.md` and `CLAUDE.md` and refresh its shared context using the [context maintenance guide](../../../templates/listener/docs/project-context.md), also copied as `docs/project-context.md`. The helper copies and renames the starter context files. Record the actual name, purpose requested by the user, platform scope, source paths, remaining skeleton TODOs, and commands/checks performed, including native artifact freshness and unavailable checks. Create missing context files according to that guide; preserve existing instructions. Do not carry successful template-repository checks into a generated plugin as if they were run there.

Report the created path, whether behavior was implemented or only scaffolded, the context file updated, and actual compilation, packaging, runtime checks, and remaining limitations. Do not stop at reporting scaffold creation when the user also requested behavior.
