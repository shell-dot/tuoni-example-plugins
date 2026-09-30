---
name: new-listener
description: Create a named Tuoni listener plugin from this repository's listener template, including Java, Windows, Linux, resource, and build-file renames.
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

Without `--folder`, the destination is `listener_<normalized-name>` under the user's original directory. A relative `--folder` is also relative to that directory; an absolute folder is used directly. The helper refuses any existing destination and omits generated build outputs. If the destination exists, report that conflict and preserve it; do not delete it or silently choose a different folder. Only after successful creation, use the returned destination as the root for validation/build commands.

The helper preserves the normalized command/listener name while prefixing Java package components that start with digits or are reserved words. Use the generated identifiers and paths rather than reconstructing them from the display name.

The helper keeps these renamed locations in sync:

- `java-plugin/src/main/java/`: package and source directory; `TemplateListener`, `TemplateListenerPlugin`, and `TemplateConfigurationSchema` class names, filenames, and references.
- `java-plugin/src/main/resources/META-INF/services/`: provider class name. Keep the SDK interface filename.
- `java-plugin/settings.gradle.kts` and `build.gradle.kts`: project name, group, `Plugin-Id`, display name, description, and Linux resource filename.
- `exec-code/win/`: solution and project filenames, solution project name and GUID, C# namespace, `RootNamespace`, `AssemblyName`, and post-build Windows shellcode resource path.
- `exec-code/linux/`: listener source folder, compiler input, and output library name. Keep the exported `run` function.
- `TemplateListener` resource constants, `scripts/docker/Dockerfile`, `Makefile`, and copied `README.md`: Windows shellcode, Linux library, JAR, executable, and build paths.

Keep `QQQWWWEEE` as the Windows pipe-name placeholder. The helper leaves behavior TODOs and the generic `ShellcodeResource` utility name intact. After creation, read the copied `AGENTS.md` and `CLAUDE.md` before further edits or validation; follow their context links.

Check generated identifiers against the requested name and check referenced paths. A requested name containing "Template" is legitimate; do not treat every occurrence as stale. Verify that the `listener-conf`, `listener-logic`, and `listener-output` skills were copied under the destination's `.agents` and `.claude` skill trees and their links resolve to the copied `docs/` files.

From the generated plugin root, compile Java with `bash java-plugin/gradlew -p java-plugin compileJava` (POSIX) or `.\java-plugin\gradlew.bat -p java-plugin compileJava` (PowerShell). Compile the Windows solution and Linux library when their tools are available. Follow the copied [build guide](../../../templates/listener/docs/building.md) for native resource generation and full JAR checks; the same guide lives at `docs/building.md` in the new plugin. A Java compile or a Windows build with its post-build event disabled does not verify a packaged plugin.

Leave the template's behavior TODOs in place unless the user asked to implement the listener.

When implementing Java/exec-unit data exchange, choose and document a payload format suited to the requested data, such as UTF-8 text, JSON, or explicitly laid-out binary fields. Match Java encoding/decoding to every native implementation. Use Java's standard text/binary APIs, or declare and bundle a parser dependency when needed. Keep the native helpers responsible for the separate [host IPC framing](../../../templates/listener/docs/execunit-ipc.md); the Java SDK hands the plugin the inner payload bytes. No external server checkout is needed to define or encode that payload.

Before finishing, read the generated plugin's `AGENTS.md` and `CLAUDE.md` and refresh its shared context using the [context maintenance guide](../../../templates/listener/docs/project-context.md), also copied as `docs/project-context.md`. The helper copies and renames the starter context files. Record the actual name, purpose requested by the user, platform scope, source paths, remaining skeleton TODOs, and commands/checks performed, including native artifact freshness and unavailable checks. Create missing context files according to that guide; preserve existing instructions. Do not carry successful template-repository checks into a generated plugin as if they were run there.

Report the created path, the context file updated, and successful compilation, packaging, and unavailable checks.
