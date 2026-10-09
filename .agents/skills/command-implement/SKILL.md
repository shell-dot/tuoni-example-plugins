---
name: command-implement
description: Implement or finish an existing Tuoni command in workspace/commands when the target is named or clear from conversation context. Routes the complete requested plugin behavior to that plugin's local skill; explains missing or ambiguous targets.
---

# Existing command: implementation

For Windows `native-lib` work, carry the hard [no authored exceptions requirement](../../../templates/command/docs/native-memory-safety.md#windows-no-authored-exceptions) into the local skill, including older copies: no project-authored throw/rethrow or exception-based error handling; require checked status/results.

For C++ changes, carry the [native memory-safety review](../../../templates/command/docs/native-memory-safety.md) into the selected local skill, including older copies. Review ownership, bounds, API failures, and concurrency; investigate memory faults with isolated local tests. Record actual diagnostic evidence separately from compilation.

This is the repository-root router for `command-implement`. Before editing, read and follow the [workspace routing guide](../../../.agents/references/workspace-skills.md). Operate only on an existing command under this repository's `workspace/commands/`.

Consult the routing guide's [current template defaults](../../../.agents/references/workspace-skills.md#current-template-defaults), then verify the selected copy's actual behavior. Extend its implemented helpers and hooks within the user's scope.

Resolve the target from the current prompt or unambiguous conversation context. A sole candidate, a recent timestamp, or a similar name does not identify the user's intended target. If no target is clear, inventory candidates and explain what the user must specify; do not start implementation or create a plugin.

Use the [read-only resolver](../../../tools/resolve_workspace_plugin.py) from the located repository:

```text
python "<repo-root>/tools/resolve_workspace_plugin.py" command implement --target "<selected-name-or-path>"
```

Use Python 3.9+ (`python3` where needed). Omit `--target` to inventory candidates when the target is unclear. Add `--client claude` when using the Claude copy. Follow the guide's handling for every non-ready result; continue only on `ready`.

State the selected plugin `path`, read its applicable `AGENTS.md` and `CLAUDE.md`, then read and follow the exact local `skill_path` returned by the resolver. Pass the complete user request, accepted decisions, and platform/scope limits to that skill. Resolve its relative references from its own directory and use the returned `path` as the working directory for plugin commands.

Carry the [command completion gate](../../../templates/command/docs/command-completion.md) into the selected plugin, including older local skill copies. Every command exec-unit must report its outcome before `Main`, `start`, or `run` returns: exactly one checked `sendReturnSuccess()` on success or `sendReturnFailed()` on failure, while the reporting connection is usable. **`sendError(...)` only sends diagnostic text; it does not mark the command failed and never replaces `sendReturnFailed()`.** Keep one completion owner for all paths, including empty output, early failure and cancellation. Verify actual host final state and explicit startup/transport failure handling; no silently unfinished command or false delivery claim.

Carry the [Java artifact and initialization gate](../../../templates/command/docs/java-verification.md) into the selected plugin, including older copied skills: verify actual SDK APIs, bundle plugin-owned runtime dependencies, inspect the exact exported JAR and run isolated provider startup/factory checks in Docker. Ordinary Gradle tests or server-installed libraries must not supply missing private classes. Record the JAR hash and startup result; a full build alone does not prove initialization. Use existing local verification helpers, or apply the guide with this repository's checker when an older plugin lacks it.

Carry the [failure-path cleanup gate](../../../templates/command/docs/native-runtime.md#failure-path-cleanup-before-return) into the local skill, including older copies. For native paths being implemented or changed, establish scoped cleanup before behavior, audit every return/throw/error send, and prove all owned work is stopped and resources released before `run` returns. Failed error delivery must not crash the host or bypass cleanup. Require forced failure and immediate unload/repeated-invocation checks; a successful build alone does not establish stability.

For this plugin task, require actual execution of the complete Docker `make build` from the selected plugin root after the final code/build-input change, even for a focused Java/configuration/output edit. Wait for its result, fix build errors and rerun the full pipeline, and verify the native exports and packaged JAR. Pass this requirement to older copied skills too. Record the command, working directory, exit status and artifact paths. A partial compile or proposed command is insufficient. Honor explicit user build overrides; if Docker is missing or unusable, inform the user and report the build blocked without a local fallback.

Load the returned file directly; calling `command-implement` again by name could re-enter this root router. Complete the requested work under the local skill, maintain that plugin's context, and report its path with actual changes/checks and remaining limitations.
