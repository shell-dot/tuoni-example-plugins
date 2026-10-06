# Routing skills to an existing workspace plugin

Agent reference: read this file when a workspace routing skill links here.

Use this guide for repository-root `command-{implement,conf,logic,output}` and `listener-{implement,conf,logic,output}` skills. These are entry points to the skills copied into each generated plugin. They remain discoverable even when the workspace is empty; eligibility is checked before any plugin work.

## Locate the repository and select a target

Resolve `../../..` from the root router's skill directory (`.agents/skills/<name>/` or its `.claude` mirror). Confirm `tools/resolve_workspace_plugin.py` and `templates/<kind>/` exist. Keep the original working directory while resolving relative user paths.

The eligible locations are `<repo-root>/workspace/commands/<name>` and `<repo-root>/workspace/listeners/<name>`. Use only the kind named by the invoked skill. A command and listener with the same name are distinct projects.

Select a target in this order:

1. Use an explicit name/path in the current request. It overrides an earlier target. A missing or invalid explicit target must not fall back to a previous or similarly named plugin.
2. Otherwise use an unambiguous active target from the conversation: for example, the plugin just created successfully, or the plugin the user explicitly selected and has continued discussing. A brief unrelated question does not clear a still-unambiguous target. Recheck its existence and kind before proceeding.
3. If neither identifies one plugin, run the resolver without a target and explain the result. Even one existing plugin does not establish intent. Do not select by directory order, modification time, the user's general feature description, or a remembered target when several have been discussed and the reference is unclear.

If the user identifies multiple targets, ask which one to use unless they explicitly request applying the task to each. For an explicit batch, resolve every named target before editing and follow each plugin's local skill separately.

## Validate without changing files

Use Python 3.9+ to run the [resolver](../../tools/resolve_workspace_plugin.py):

```text
python "<repo-root>/tools/resolve_workspace_plugin.py" command output --target "daily-check"
python "<repo-root>/tools/resolve_workspace_plugin.py" listener conf --target "workspace/listeners/beacon" --client claude
python "<repo-root>/tools/resolve_workspace_plugin.py" command implement
```

The positional arguments are kind (`command` or `listener`) and action (`implement`, `conf`, `logic`, or `output`). The last example inventories command candidates without selecting one. The resolver returns JSON; `ready` permits delegation, while a non-ready result explains why selection cannot proceed. Non-ready results use exit code 2.

On `ready`, `path` is the selected plugin's root and `skill_path` is the local instruction file to read. The separate `root` field identifies this helper repository. Use `path` as the working directory for plugin work. `candidates` lists eligible choices and never selects one by itself.

The resolver checks workspace containment, plugin structure and kind, and the requested local skill. It accepts an existing folder name, a normalized display name such as `Daily Check`, or a path identifying the plugin root. Explicit relative paths are resolved from the original working directory; repository-relative `workspace/...` paths are also supported. Conflicting path interpretations require clarification. It prefers `.agents`, or `.claude` with `--client claude`, and can use the other local copy when the preferred file is absent.

Do not create directories, scaffold a replacement, copy a template skill into an existing project, or edit a guessed target to make validation pass. Do not run a template's skill as a substitute for the selected plugin's local skill. Files outside the workspace require working directly in that project's context; these root routers are for workspace plugins.

## Explain unresolved targets

Give a short explanation and a concrete next step:

- No matching plugins: say which workspace category was checked and that no eligible plugin was found. Point to `new-command` or `new-listener` for creation; do not invoke it automatically.
- Target missing or invalid: identify the requested target and the resolver's reason. List relevant existing candidates, if any, and ask for the correct name/path.
- Target unclear: list the existing names/paths and ask which one the user means. If only one exists, still ask whether it is the intended target.
- Missing local skill or incomplete scaffold: explain the exact missing item. Preserve the plugin; do not overwrite its files or silently substitute the repository template.

For example: "I found commands `daily-check` and `inventory`, but this request does not identify one. Which should `command-output` apply to?" With no listeners: "No listener plugins were found under `workspace/listeners`. Create one with `new-listener` before using `listener-conf`."

Wait for the missing target information before dependent work. A name inferred from an unrelated example or silence after a question is not a selection.

## Current template defaults

For terminology and the distinction between source families and generated
formats, see the [command overview](../../templates/command/docs/execunit-overview.md)
and [listener overview](../../templates/listener/docs/execunit-overview.md).
New copies include their own `docs/execunit-overview.md`. Prefer the selected
plugin's local documentation and source; a template overview is not evidence of
behavior in an older or customized plugin.

New command copies accept `{}`, serialize zero native payload bytes, connect through
the utilities, emit exact UTF-8 `DONE`, and report success. Java appends the text to
`output`. New listener copies accept `{}`, implement local Java lifecycle and empty
replacement encoding, connect native pipe/FIFO utilities, and idle until host
disconnect. Their data traffic channel remains intentionally TODO. See the
[command default](../../templates/command/README.md#default-behavior) and
[listener default](../../templates/listener/README.md#default-behavior).

Verify the selected plugin's source before applying these facts: older or customized
copies can differ. Extend working helpers and lifecycle ownership; implement only
the requested behavior. A listener formatting or idle-startup task does not require
adding a traffic channel. Do not add command terminal reports to a listener or treat
Java STARTED as observed remote readiness.

## Requested support subsets

Carry explicit OS, architecture, and exec-unit-format limits into the selected
plugin's local skills. Use its `docs/support-scope.md` when present. The current
[command guide](../../templates/command/docs/support-scope.md) and
[listener guide](../../templates/listener/docs/support-scope.md) explain how to
interpret and record these limits; verify facts against the selected plugin.
Generic all/every coverage instructions do not override an explicit limit.
Separate support restrictions from task-only or test-only limits, and retain
existing coverage on unspecified dimensions. Report requested, advertised,
implemented, and verified support separately; an unavailable check is not an
implicit decision to drop support. Do not overwrite older plugin guidance to
add these references.

## Build and byte-verification defaults

Carry these defaults into the selected plugin task unless the user explicitly overrides them, including when its copied local skill predates these requirements:

- For every configuration, implementation, logic, or output task, actually execute the selected plugin's complete Docker `make build` after substantial coherent steps and after the final code/build-input change, even for Java-only edits. Wait for completion and verify all in-scope native exports plus the packaged Java plugin; a planned command, readiness check or partial target is insufficient. Record the command, working directory, exit status and artifact paths. Use Docker for every build unless the user explicitly requests another route. Check the client, daemon, Linux containers and required shell/Make route. If Docker is missing or unusable, inform the user of the specific blocker and mark the affected builds blocked; do not fall back to local tools. Fix source/build errors and rerun the complete pipeline before reporting build success. Report unavailable phases without silently dropping platforms.
- Verify actual Java configuration bytes against each native decoder, then separately through the actual native connection helper with verified startup framing. Outgoing SDK configuration buffers must start at position zero with an exact payload limit. Test native-produced responses through the real Java receiver/parser and check the final JAR contains the matching native artifacts.
- Keep host IPC framing separate from plugin payloads. Do not guess initial message tags or accept malformed input merely to suppress a configuration-frame error. Record payload-codec, framed-transport, build and runtime evidence separately.

Use the selected plugin's own paths, build files and established contracts. Current references are the [command build checkpoints](../../templates/command/docs/building.md#required-build-checkpoints), [command byte checks](../../templates/command/docs/payload-verification.md), [listener build checkpoints](../../templates/listener/docs/building.md#required-build-checkpoints), and [listener byte checks](../../templates/listener/docs/payload-verification.md). Apply them to the selected plugin without editing the source template or replacing its local skill.

## Command terminal outcome

For command tasks, carry the [command completion gate](../../templates/command/docs/command-completion.md) into the selected plugin even when copied local skills predate it. Every invocation reaches one completion owner; every usable-channel success/failure/cancel/early-exit path has one checked terminal outcome before closing the report channel and returning. Require empty-success and failed-error-formatting cases, observe actual host final state, and verify supported startup/disconnect failure propagation so commands cannot silently remain pending. No false claim of delivery over a broken connection. These command terminal APIs do not apply to listener transport traffic.

## Java artifact and initialization checks

Carry the [command Java gate](../../templates/command/docs/java-verification.md) or [listener Java gate](../../templates/listener/docs/java-verification.md) into the selected task even when its local skills predate it. Verify actual SDK signatures and library ownership, package plugin-owned runtime dependencies with all required transitive classes/resources, then check the exact Docker-exported JAR and execute isolated provider initialization/schema/factory tests. Keep private dependencies off the parent/test classpath so a thin JAR cannot pass by using server or Gradle libraries. Preserve actual failures and record artifact path/hash, archive check, and startup results separately from compilation.

New plugins include `scripts/verify_java_artifact.py`. For an older plugin without it, invoke the [repository checker](../../templates/command/scripts/verify_java_artifact.py) by absolute path against the selected plugin's explicit JAR and kind; its ZIP checks are kind-neutral and do not require copying or replacing that plugin's local skills. The archive check is followed by a plugin-specific isolated startup fixture. A required SDK/loader fixture that is unavailable is an unverified check, not a passing test.

## Failure cleanup and stability

Carry this requirement into older local skill copies as well: implement per-invocation ownership and nonthrowing cleanup before native operation logic. On every startup, execution, cancellation, disconnect and reporting failure, stop producers, unblock owned operations, unregister/drain callbacks, join workers, release resources and only then return from `run`. Review reused helpers; trailing manual cleanup and detached work are not sufficient. Error diagnostics are bounded and fallible; command terminal reporting remains mandatory on a usable connection under the command completion gate. Reporting must not terminate the host or bypass cleanup.

Apply the [command failure-path gate](../../templates/command/docs/native-runtime.md#failure-path-cleanup-before-return) or [listener failure-path gate](../../templates/listener/docs/native-runtime.md#failure-path-cleanup-before-return) to the selected project. Require regressions for operation failure, partial startup, failed reporting/disconnect and worker failure, with host survival and immediate compatible-loader unload/repeated invocation. Keep actual lifecycle evidence separate from the full Docker build and record unavailable runtime checks.

## Delegate within the selected plugin

After a `ready` result, briefly state the selected plugin name/path. Read its applicable `AGENTS.md`, `CLAUDE.md`, and the exact returned `skill_path`; use the returned plugin root for subsequent commands. Transfer the original request, accepted decisions, and constraints, including platform limits and any explicit exclusions.

The root router and local implementation skill intentionally share a name. Follow the returned file directly, not a second short-name invocation, to avoid routing back here. Relative links in the local skill point to that plugin's sibling skills and docs. Preserve the local workflow, host-process/unload requirements, and project-context maintenance.

A validated destination is not permission to expand the task. Follow the requested action and report actual implementation/build/runtime results under the selected plugin's local skill.
