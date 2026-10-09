# Understanding the listener exec-units

Read this orientation after the plugin's [project context](../AGENTS.md), before
the detailed skill workflow. It describes the source template's existing idle
behavior. In a generated or customized plugin, check the local files: names and
behavior can differ from this starting point.

For a subset of OSs, architectures, or formats, read [support scope](support-scope.md).
The full inventory below describes the starting template; it does not override
the developer's explicit support limits.

## Terms and boundaries

| Term | Meaning in this template |
| --- | --- |
| Exec-unit | The component that runs inside the agent host. It is separate from the Java server plugin. |
| Source family | One implementation in one language/platform directory. There are three families below. |
| Entrypoint | The first function called in an exec-unit; it coordinates that invocation's lifetime. |
| Artifact / format | A generated representation of source code. Several formats can share one source family. |
| Helper | Shared support code used by an entrypoint, such as connection and resource management. Its presence does not mean every optional feature is active. |
| Java plugin | Server-side validation, local lifecycle state, artifact selection, and information display. Its JAR is not another exec-unit. |
| Local host connection | The existing connection between an exec-unit and its agent host. It is not the listener's application traffic channel. |
| Application traffic channel | The separate data path left as TODO in this template. Successful local startup does not establish it. |

The Java plugin and exec-unit run in different processes. "Started" can describe
the Java object's local state without describing an active network endpoint or
observed remote health. Those claims need different evidence.

## All source families and formats

| Source family | Starting source | Advertised artifacts | Existing default |
| --- | --- | --- | --- |
| Managed Windows, C# | [Program.cs](../exec-code/win/Program.cs) | Windows x86/x64: `SHELLCODE_NATIVE`, `DOTNET_EXE`, `DOTNET_DLL` | Validate empty configuration, wait for local disconnect, release resources. |
| Native Windows, C++ | [Main.cpp](../exec-code/win-native/listener/Main.cpp) | Windows x86/x64: `NATIVE_LIB` DLLs | The same idle behavior, with scoped utility ownership. |
| Linux, C++ | [Main.cpp](../exec-code/linux/listener/Main.cpp) | Linux x64: `NATIVE_LIB` shared library | The same idle behavior, with scoped connection ownership. |

The three managed formats share the C# behavior. The native Windows DLLs are a
separate C++ implementation, not the managed DLL under another filename. Windows
and Linux both use the `NATIVE_LIB` label but have different source and artifacts.
A format label or architecture declaration is not evidence that an artifact was
built or exercised successfully.

The managed DLL method sidecar is metadata, not a fourth source implementation.
The Java JAR packages server classes and execution resources; it does not replace
the three source families. Build output directories contain generated files,
not the authoritative explanation of the source's behavior.

## Follow the existing idle behavior

There are two separate lifetimes to understand:

| Java object | Exec-unit invocation |
| --- | --- |
| Accepts the empty configuration and stores local identity/context. | Establishes its local host connection and validates empty configuration. |
| Start changes local status. No application endpoint is opened by the default. | Waits for the local host to disconnect. No application traffic is forwarded. |
| Stop permits a later restart; delete is terminal. | Cleanup waits for its owned reader and releases connection resources. |
| Information display contains the listener identity and local status. | There is no implemented application telemetry path to enrich that display. |

Rows compare responsibilities; they do not assert that a Java method triggers the
exec-unit action beside it. In particular, Java stop is not evidence of a remote
shutdown acknowledgement, and Java reconfiguration is not evidence of a remotely
applied setting. The default has no configuration fields to change.

## What differs behind the same idle state

| Family | Where lifetime is described by the current source |
| --- | --- |
| Managed Windows | The entrypoint coordinates initialization, disconnect waiting, and final cleanup. Its utility owns the local reader. |
| Native Windows | The entrypoint observes the utility's connection state. Scoped utility cleanup owns the local reader's end of life. |
| Linux | The entrypoint uses scoped ownership and waits for its local reader to finish. |

Each family has its own source and utility implementation even though all remain
idle. A helper capable of reading data does not establish an application channel.
There is no command-style result parser or terminal command outcome in this
listener template. Do not infer those from the command template's `DONE` example.

## Implemented, placeholder, and unverified

| State | How to read the current template |
| --- | --- |
| Implemented in source | Empty configuration handling, Java local lifecycle, exec-unit local startup, disconnect waiting, and cleanup. |
| Placeholder | Application traffic, associated endpoint/session handling, and custom telemetry. Suggested classes in other guides are not existing files. |
| Unverified here | A successful build, operational connectivity, or safe host unloading cannot be inferred from documentation or declared format support. Consult recorded checks. |

Use the [README default](../README.md#default-behavior) for the public starting
contract and [AGENTS.md](../AGENTS.md) for current project facts. Identify the
source family before interpreting a file. Keep source review, compilation,
packaging, and runtime observations separate when reporting results.

For a documentation-only review, check the linked files, terminology, and skill
mirrors. Documentation checks establish no new build or runtime evidence. This
guide is copied with the plugin; its relative links should resolve within that
copy. [Context maintenance](project-context.md) explains where to record changed
facts without carrying template verification into a new instance.
