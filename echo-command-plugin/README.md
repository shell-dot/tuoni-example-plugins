# Tuoni Plugin Examples

Welcome to the Tuoni Plugin Examples repository!

This repository contains example plugins for the [Tuoni](https://github.com/shell-dot/tuoni) Command and Control (C2) framework. \
Each plugin consists of two parts:

1. **Agent execunits**: Windows shellcode/.NET EXE/.NET DLL written in C#, plus Windows x86/x64 and Linux x64 native libraries written in C++.
2. **Server Plugin**: Written in Java against the Tuoni plugin SDK, requiring Java 21+ and Gradle for building.

For a minimal command starting point, use the [command template](../templates/command/README.md).
It already connects native IPC, accepts `{}`, returns `DONE`, and displays that text
with success completion. This echo example provides additional command patterns.

## Table of Contents

- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Building the Server Plugin](#building-the-server-plugin)
- [Plugins](#plugins)

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed on your machine:

- Java 21+
- Gradle
- Docker and Make for building the Linux execunits

### Building the Server Plugin

From `echo-command-plugin/`, build all execution formats and the Java plugin:

```sh
make build
```

This builds fresh Windows shellcode, AnyCPU managed EXEs/DLLs, Windows x86/x64 native DLLs, and
Linux x64 native libraries inside Docker and exports them with the JAR to `build/`.
All four command templates advertise `SHELLCODE_NATIVE`, `DOTNET_EXE`,
`DOTNET_DLL`, and `NATIVE_LIB`. Windows x86/x64 agents receive the Windows
formats; Linux x64 receives the native library with the `run` export.
Managed assemblies are delivered unchanged and receive the pipe name in `args[0]`.
DLL entrypoints are read from the generated `<command>.dotnet_dll_method` file,
which names the public `<namespace>.Program::start` wrapper.

`make build-dotnet` exports `.dotnet_exe`, `.dotnet_dll`, and `.dotnet_dll_method`
for each command, plus the legacy shellcode-input `.exe`, without conversion or
Java compilation. The JAR stores managed resources beside shellcode under
`shellcode/`. Its build checks require all formats and run `execUnitFormatsCheck`
to verify platform selection, entrypoints, PE DLL/EXE roles, and resource bytes.
These Java checks do not execute native code or establish host/unload safety.

For a direct Java build, first build the default Release solution (shellcode),
the solution with `/p:ExecUnitFormat=dotnet-exe`, the solution with
`/p:ExecUnitFormat=dotnet-dll`, the Windows native DLLs, and the Linux libraries. Managed output is under
`exec-code/win/<command>/bin/Release/dotnet-exe/` or `dotnet-dll/`; then run
`sh gradlew build` from `java-plugin/`.

For Windows agents that report no exec-unit capabilities, the commands also
support the server's legacy shellcode fallback. Linux native libraries still
require the agent to advertise `NATIVE_LIB` support.

## Plugins

Here is a list of the example plugins included in this repository:

* **Echo Command Plugin (contains 4 commands)**
  - **Server Plugin**: `java-plugin/`
  - **Windows shellcodes solution**: `exec-code/win/echo-commands.sln`
  - **"echo" command**
    - **Description**: Demonstrates most simple type of command
    - **Command class in Java**: `EchoCommand`
    - **Command template class in Java**: `EchoCommandTemplate`
    - **Shellcode project**: `echo`
  - **"echo-ongoing" command**
    - **Description**: Demonstrates command where result is returned over time
    - **Command class in Java**: `EchoCommandOngoing`
    - **Command template class in Java**: `EchoCommandOngoingTemplate`
    - **Shellcode project**: `echo-ongoing`
  - **"echo-ongoing-file" command**
    - **Description**: Demonstrates file type configuration value and stopping handler in shellcode
    - **Command class in Java**: `EchoCommandOngoingFile`
    - **Command template class in Java**: `EchoCommandOngoingFileTemplate`
    - **Shellcode project**: `echo-ongoing-file`
  - **"echo-ongoing-more-data" command**
    - **Description**: Demonstrates how to send additional data to already running job and manage job object from the plugin
    - **Command class in Java**: `EchoCommandOngoingMoreData`
    - **Command template class in Java**: `EchoCommandOngoingMoreDataTemplate`
    - **Shellcode project**: `echo-ongoing-more-data`

Additionally, there is a set of .NET utility classes that facilitate communication between the command shellcode and the agent. These are located at `exec-code/win/exec-unit-utils` and are implemented as a shared code project, which is referenced and used by the shellcode solution. These are also available at [tuoni-execunit-utils-dotnet](https://github.com/shell-dot/tuoni-execunit-utils-dotnet) repository.

The local managed copies include defensive framing and cleanup changes documented
in [their provenance notes](exec-code/win/exec-unit-utils/README.md). Echo startup,
configuration, reporting, and cleanup share one exception boundary. More-data
callbacks queue input; the invocation processes updates preceding stop in order
and returns after host disconnect. These lifecycle changes still require compiled
runtime verification.

Each plugin folder contains both the agent execunit source code and the Java plugin source code.
Windows shellcode output is at `exec-code/win/{command}/bin/Release/{command}.shellcode`. The server plugin JAR is at `java-plugin/build/libs/tuoni-example-plugin-echo-command-0.0.1.jar`.

### Linux execunits

Run `make build-linux` with Docker to compile all four Linux x64 native shared
objects in an Ubuntu 18.04 amd64 container. The target writes them to `exec-code/linux/build/` for
Gradle and copies them into `build/`. The sources and FIFO/TLV protocol implementation are
under `exec-code/linux/`: `echo/`, `echo-ongoing/`, `echo-ongoing-file/`, and
`echo-ongoing-more-data/` each contain their own `Main.cpp`. `make build` builds
both platforms inside Docker and packages them in the plugin JAR. The JAR and
both platforms' artifacts are exported to `build/`; `BUILD_DIR` overrides that location.

The Java command templates accept Windows and Linux shellcode agents. Windows shellcode payloads
retain their UTF-16LE pipe-name patch; Linux payloads use the native `run` export and
receive their FIFO paths from the agent loader.


---

Happy coding!

For more information on the Tuoni C2 framework, visit the [official Tuoni GitHub repository](https://github.com/shell-dot/tuoni).

## Windows native libraries

Run `make build-windows-native` to cross-compile Windows x86/x64 DLLs in Docker
using MinGW. Native source lives under `exec-code/win-native/`. Each DLL exports
exactly `start(const char* pipeName)`; Java selects `.native32_dll` or
`.native64_dll` using the agent process architecture and passes the bytes unchanged.
The pipe/configuration and result/TCP protocols match the other formats.
`make build` embeds and exports these DLLs with the Java plugin; the standalone
target also writes them to `exec-code/win-native/build/` for direct Gradle builds.

The native commands use `CommunicationNamedPipesCommand` and `TLV`, copied from
`commands_default/common/CommonCppExecUnit` into
[`exec-unit-utils/`](exec-code/win-native/exec-unit-utils/README.md). The utility
sources are unchanged; the build supplies a MinGW header-name compatibility shim.
It also force-includes a guarded compatibility header for the Windows error code
`ERROR_UNHANDLED_EXCEPTION`, which some MinGW headers omit.
Callbacks record updates/stop requests, while command execution and output stay on
the invocation thread. All four variants share one checked terminal-report owner.
Cleanup cancels I/O and joins the pipe reader before callback state is destroyed.
The build's [PE verifier](scripts/verify_windows_native.py) checks architecture,
the sole `start` export, absence of a CLR header and OS-only DLL dependencies.

After building, use Windows Python matching the DLL architecture to run local IPC,
failure/disconnect, repeated invocation and immediate unload checks:

```powershell
python scripts/check_windows_native_runtime.py build/echo.native64_dll --mode echo
```

Use a 32-bit Python for `.native32_dll`. For the echo variants, pass the matching
DLL and `--mode echo-ongoing`, `echo-ongoing-file`, or `echo-ongoing-more-data`.
The
[check harness](scripts/check_windows_native_runtime.py) runs each case in a child
process with a watchdog; it does not replace real Tuoni agent integration tests.
