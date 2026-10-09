# Patterns from existing command plugins

Use this reference when adapting configuration, execution, or results from Tuoni's existing implementations. The source pairs below were inspected together with shared helpers and focused tests. Choose the closest data-flow pattern; preserve this plugin's requested behavior and platform scope.

For a fresh plugin, begin with the [minimum implementation recipe](implementation-recipes.md); use this map when a step needs a concrete reference. Copy the required responsibility into the template's existing class structure. A server template inheriting `SimpleStatelessExecUnitCommandTemplate` puts its factory/result hooks in different classes from this standalone template.

The [current template](../README.md#default-behavior) already supplies empty-object validation, native IPC startup, `DONE` text presentation, and checked completion. Adapt an existing pair for the requested operation; preserve those working hooks instead of copying helper boilerplate wholesale.

## Locate a matching pair

Reference checkouts are commonly siblings named `commands_default`, `listeners_default`, and `tuoni-server`. The server sources are under `plugin/` (singular). Locate the actual roots with `rg --files`; a generated plugin may live elsewhere. The guidance here remains usable without those checkouts. Treat source paths below as locators within the named repository, not dependencies that must be present in the generated plugin.

Java classes below live in the named module's `src/main/java/com/shelldot/tuoni/plugin/` package tree.

| Concern | Java counterpart in `tuoni-server/plugin/` | Native counterpart in `commands_default/` |
| --- | --- | --- |
| Typed configuration and paired encoders/decoders | `fs-commands`: `FsCommandConfigurationFileCopy`, `FsCommandTemplateCopy` | `commands/fs_copy/execunits/windows/fs_copy_dotnet/Conf.cs`; `commands/fs_copy/execunits/posix/Main.cpp` |
| Multipart file input | `fs-commands`: `FsCommandConfigurationFileWrite`, `FsCommandTemplateWrite` | `commands/fs_write/execunits/`; inspect the actual decoder before changing fields |
| Repeated structured results | `os-commands`: `OsCommandTemplateProcinfo.parseResult` | `commands/os_procinfo/execunits/windows/os_procinfo_dotnet/ProcinfoMain.cs`; `commands/os_procinfo/execunits/posix/Main.cpp` |
| File stream and hidden progress | `fs-commands`: `FsCommandTemplateRead.parseResult` | `commands/fs_read/execunits/linux/Main.cpp` |
| Structured multipart decoding/merging | `os-commands`: `service/ServiceProtocol`, `ServiceResultMerger`, `OsCommandTemplateServiceBase`; `src/test/.../ServiceProtocolAndMergerTest` | Inspect the corresponding `commands/os_service/execunits/` protocol files when changing that established contract |
| Shared template and artifact loading | `common`: `SimpleStatelessExecUnitCommandTemplate`, `SimpleStatelessCommandTemplateBase`, `TemplateLoader`, `DotnetDllEntrypoint` | Shared project imports and platform build manifests |

Compare the user's requested behavior with the source pair, then adapt only the useful responsibility. Existing formats and incomplete validation are compatibility references, not defaults for a new command. The `fs_read` configuration is raw UTF-8 and its output is a filename-length stream; these show that inner payloads need not use the host envelope format. Keep the generated plugin's payload choice simple and explicit.

## Configuration

Model the full handoff: user JSON/files -> validated typed configuration -> payload bytes -> native typed configuration. Compare both generation methods and every native decoder. Inspect actual returned bytes and the native receiver rather than inferring a format from a method name.

For each changed field, record encoding, scalar width/signedness, units, bounds, cardinality, omission/default semantics, and startup/update behavior. Retain established field meanings and document changes to the wire layout.

The copy example passes the same encoded source/destination fields through both Java generation methods to managed and POSIX decoders. Its native path expansion/trimming and Java path validation are operation-specific choices. The write example distinguishes a file part, its name, and its bytes; use bounded reads from the [configuration guide](configuration.md) when adopting that pattern.

Attach the selected multipart file to the typed candidate **before** validation that reads its name/content, then validate any resolved destination. The reviewed `FsCommandTemplateWrite.parseConfiguration` calls `validateLogic` before `withFile`; its validator can dereference the still-null file when `filepath` is absent. Copy its field/byte handoff, not that ordering.

Existing server bases use `ConfigurationHelper`, validation annotations, and optional default merging. Those are implementation dependencies in `plugin-common`, not SDK APIs. A standalone plugin must explicitly supply equivalent validation/default behavior or a compatible dependency. Keep uploaded parts attached through any JSON default-merge step. For a field rename in an existing deployed plugin, inspect its configuration migration path as well as the native wire contract.

## Source ownership and compatibility

The default command tree separates shared managed logic from EXE, DLL, and shellcode launchers. `.projitems` and `.vcxitems` identify compiled sources. Several POSIX platform files only include `../posix/Main.cpp` (for example `fs_copy` and `os_procinfo`). Edit the owning source, include it once, and compare truly independent platform implementations.

Reusable helper locations include `common/CommonClasses`, `CommonCppExecUnit`, and `CommonLinuxExecUnit` / `CommonBsdExecUnit` / `CommonMacExecUnit`. The managed command adapter is `CommandCommunicationNamedPipes`; template naming differs. The reviewed `CommunicationNamedPipesOptions.StructuredCommand()` supplies bounded I/O and exact host envelopes. Its compatibility profile has different limits, and the structured profile disables request/response support. Select/adapt the profile to the actual command; do not transplant it without checking required callbacks and responses.

Build a support matrix from OS, **process** architecture, exec-unit type, native implementation, artifact, and loader entrypoint. An x86 process can run on an x64 OS. Validate both advertised support and direct generation calls; an unsupported architecture must not fall through to an x64 resource. Existing plugin breadth does not require adding extra platforms to this scaffold.

Prefer state owned by one invocation. A shared Java template or a process-global native callback/cancellation flag can be used concurrently by different commands. Trace state lifetime and cleanup before copying an asynchronous example. Preserve established drain behavior until the actual transport proves completion; a fixed sleep is not a general flush mechanism.

Use the [native map](native-runtime.md) for the template's ownership changes and the [build guide](building.md) for dependency, artifact, and entrypoint checks.

## Results and state

`os_procinfo` demonstrates native collection separated from Java rendering of repeated name/value records as text and JSON. Reuse the presentation responsibilities when useful; a new command can use a simpler agreed payload format. Keep stable result names when extending a plugin.

For multipart results, the service implementation separates `ServiceProtocol` decoding, `ServiceResultMerger` state transitions, and rendering. It validates record shape, sequence, flags, and bounds, then publishes public results and plugin-only stream state together. Adopt the responsibilities needed by the requested result, without copying service-specific fields, limits, or operation semantics. Keep any necessary structural bounds checks in a shared decoder rather than proliferating independent payload parsers.

State belongs to the command execution. This template has a distinct command object. The shared `SimpleStateless*` pattern calls the same template parser for multiple executions and passes `previousResult`; its fields are not per-command storage. If reconstructing persisted state, validate version and command/request identity before using it, and reject inconsistent pairs of public data and internal stream state.

The `fs_read` Java parser uses hidden progress entries and downloadable-file APIs. Its early returns on incomplete filename data do not provide a general byte accumulator. Retain the unconsumed suffix explicitly, including split metadata/length prefixes, and test every meaningful boundary. See the [output guide](output.md) for strict decoding, file values, and final notifications.

## Focused verification

Select checks for the changed contract rather than compiling unrelated plugins:

- Encode representative configuration with Java and decode it in every native implementation; send native result fixtures through Java. Include omitted/default fields, repeated values, Unicode, exact scalar widths, and unknown/duplicate fields where applicable to the chosen representation.
- For multipart data, test two interleaved commands, split headers/values, duplicate/out-of-order chunks when the protocol defines sequences, empty final notifications, missing terminal records, and partial/failure results. Assert preserved bytes and visible result entries.
- Follow `ServiceProtocolAndMergerTest` for byte fixtures shared by managed/native encoders and semantic rejection cases. Verify the fixture against each encoder; a Java round trip alone cannot prove cross-language agreement.
- Use a local protocol harness for stop, disconnect, short reads/writes, and worker cleanup. Exec-units expect a compatible pipe/FIFO peer; launching one directly is not a useful smoke test.
- Validate the supported resource combinations and rebuilt JAR contents. Compilation, artifact format checks, and runtime behavior are separate results.
