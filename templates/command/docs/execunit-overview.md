# Understanding the command exec-units

Read this orientation after the plugin's [project context](../AGENTS.md), before
the detailed skill workflow. It describes the source template's existing no-op
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
| Java plugin | Server-side registration, validation, artifact selection, and result presentation. Its JAR is not another exec-unit. |
| Payload bytes | Data belonging to this command, such as configuration or result text. This use of "payload" does not mean a payload-program template. |

The Java plugin and exec-unit run in different processes. The local host
connection is a separate layer from the command's configuration and result data.
Do not infer Java behavior from a similarly named C# or C++ helper.

## All source families and formats

| Source family | Starting source | Advertised artifacts | Existing default |
| --- | --- | --- | --- |
| Managed Windows, C# | [Program.cs](../exec-code/win/Program.cs) | Windows x86/x64: `SHELLCODE_NATIVE`, `DOTNET_EXE`, `DOTNET_DLL` | Validate empty configuration, produce `DONE`, report the outcome, release resources. |
| Native Windows, C++ | [Main.cpp](../exec-code/win-native/command/Main.cpp) | Windows x86/x64: `NATIVE_LIB` DLLs | The same no-op result, with lifecycle ownership in a shared native wrapper. |
| Linux, C++ | [Main.cpp](../exec-code/linux/command/Main.cpp) | Linux x64: `NATIVE_LIB` shared library | The same no-op result, with scoped connection ownership. |

The three managed formats share the C# behavior. The native Windows DLLs are a
separate C++ implementation, not the managed DLL under another filename. Windows
and Linux both use the `NATIVE_LIB` label but have different source and artifacts.
A format label or architecture declaration is not evidence that an artifact was
built or exercised successfully.

The managed DLL method sidecar is metadata, not a fourth source implementation.
The Java JAR packages server classes and execution resources; it does not replace
the three source families. Build output directories contain generated files,
not the authoritative explanation of the source's behavior.

## Follow the existing no-op once

1. **Java accepts configuration.** The fresh schema accepts an empty object and
   no uploaded files. There are no operation-specific settings.
2. **The exec-unit initializes.** It establishes its local host connection and
   checks the configuration. Empty configuration and failed startup are different
   conditions.
3. **The operation produces text.** The default performs no system operation; its
   only result is `DONE`.
4. **Java presents the result.** The command parser appends the text to the
   `output` result. Visible text is separate from the terminal outcome.
5. **The invocation finishes.** The source attempts one terminal outcome on a
   usable connection and releases its owned resources. A broken connection cannot
   establish successful delivery merely because a reporting function was called.

These are stages of one logical operation, not a sequence of independent
exec-units. The default has no live-update behavior. Optional helper APIs and
worked examples elsewhere do not make updates or streaming active.

## What differs behind the same result

| Family | Where lifetime is described by the current source |
| --- | --- |
| Managed Windows | The entrypoint coordinates initialization, the no-op, outcome reporting, and cleanup in a finalization block. The default installs no reader callbacks. |
| Native Windows | The short entrypoint delegates ownership to [CommandRuntime.h](../exec-code/win-native/common/CommandRuntime.h). The utility owns a reader; the short entrypoint alone is not the whole lifetime. |
| Linux | The entrypoint owns a scoped connection whose destruction releases resources. The default does not activate the optional callback reader. |

The shared visible result does not imply identical worker or cleanup behavior.
Likewise, a Java status hook does not demonstrate that exec-unit work has ended.
The project context records known lifecycle limitations and unavailable checks.

## Reading and reporting accurately

- Use the [README default](../README.md#default-behavior) for the public starting
  contract and [AGENTS.md](../AGENTS.md) for current project facts.
- Identify the source family before interpreting a file. A C# change says nothing
  by itself about either C++ implementation.
- Treat a source implementation, an illustrative example, and a TODO as different
  states. Never describe an example's fields or output as already implemented.
- Keep source review, compilation, packaging, and host runtime observations
  separate. Report a check as unverified when it was not run.
- For a documentation-only review, check the linked files, terminology, and skill
  mirrors. Documentation checks establish no new build or runtime evidence.

This guide is copied with the plugin. Its relative links should resolve within
that copy; [context maintenance](project-context.md) explains where to record
changed facts without carrying template verification into a new instance.
