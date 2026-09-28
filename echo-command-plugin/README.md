# Tuoni Plugin Examples

Welcome to the Tuoni Plugin Examples repository!

This repository contains example plugins for the [Tuoni](https://github.com/shell-dot/tuoni) Command and Control (C2) framework. \
Each plugin consists of two parts:

1. **Agent execunits**: Windows shellcode written in C# and Linux x64 shared objects written in C++.
2. **Server Plugin**: Written in Java against the Tuoni plugin SDK, requiring Java 21+ and Gradle for building.

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

Build the Linux native execunits in Docker before Gradle. From `echo-command-plugin/`, run:
```
make build-linux
cd java-plugin
sh gradlew assemble
```
Gradle compiles the Java code for Java 21 and packages both Linux execunits and
the bundled Windows shellcodes. `make build` builds fresh binaries for both
platforms inside Docker.
All four command templates advertise `SHELLCODE_NATIVE` and `NATIVE_LIB`.
Each command selects Windows shellcode or the Linux x64 native library according
to the target agent and uses the Linux `run` export as its entrypoint.

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

Each plugin folder contains both the agent execunit source code and the Java plugin source code.
Windows shellcode output is at `exec-code/win/{command}/bin/Release/{command}.shellcode`. The server plugin JAR is at `java-plugin/build/libs/tuoni-example-plugin-echo-command-0.0.1.jar`.

### Linux execunits

Run `make build-linux` with Docker to compile all four Linux x64 native shared
objects in an Ubuntu 18.04 amd64 container. The target writes them to `exec-code/linux/build/` for
Gradle and copies them into `public/`. The sources and FIFO/TLV protocol implementation are
under `exec-code/linux/`: `echo/`, `echo-ongoing/`, `echo-ongoing-file/`, and
`echo-ongoing-more-data/` each contain their own `Main.cpp`. `make build` builds
both platforms inside Docker and packages them in the plugin JAR. The JAR and
both platforms' artifacts are exported to `public/`; `BUILD_DIR` overrides that location.

The Java command templates accept Windows and Linux shellcode agents. Windows payloads
retain their UTF-16LE pipe-name patch; Linux payloads use the native `run` export and
receive their FIFO paths from the agent loader.


---

Happy coding!

For more information on the Tuoni C2 framework, visit the [official Tuoni GitHub repository](https://github.com/shell-dot/tuoni).
