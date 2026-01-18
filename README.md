# Tuoni Plugin Examples

Welcome to the Tuoni Plugin Examples repository! 

This repository contains example plugins for the [Tuoni](https://github.com/shell-dot/tuoni) Command and Control (C2) framework. \
Each plugin consists of two parts:

1. **Shellcodes**: Written in C# .NET framework.
2. **Server Plugin**: Written in Java against the Tuoni plugin SDK, requiring Java 21 and Gradle for building.

## Table of Contents

- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Building the Server Plugin](#building-the-server-plugin)
- [Plugins](#plugins)

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed on your machine:

- Java 21
- Gradle

### Building the Server Plugin

Each plugin's server part can be built using Gradle. Navigate to the individual plugin directory and run the following command:
```
./gradlew assemble
```
This command will compile the Java code and build the server plugin.

## Plugins

Here is a list of the example plugins included in this repository:

* **Echo Command Plugin (contains 3 commands)**
  - **Server Plugin**: `plugins/echo-command-plugin/`
  - **Shellcodes solution**: `shellcodes/CommandExecUnits/`
  - **"echo" command**
    - **Description**: Demonstrates most simple type of command
    - **Command class in Java**: `EchoCommand`
    - **Command template class in Java**: `EchoCommandTemplate`
    - **Shellcode project**: `CommandEcho`
  - **"echo-ongoing" command**
    - **Description**: Demonstrates command where result is returned over time
    - **Command class in Java**: `EchoCommandOngoing`
    - **Command template class in Java**: `EchoCommandOngoingTemplate`
    - **Shellcode project**: `CommandEchoOngoing`
  - **"echo-ongoing-file" command**
    - **Description**: Demonstrates file type configuration value and stopping handler in shellcode
    - **Command class in Java**: `EchoCommandOngoingFile`
    - **Command template class in Java**: `EchoCommandOngoingFileTemplate`
    - **Shellcode project**: `CommandEchoFile`
  - **"echo-ongoing-more-data" command**
    - **Description**: Demonstrates how to send additional data to already running job and manage job object from the plugin
    - **Command class in Java**: `EchoCommandOngoingMoreData`
    - **Command template class in Java**: `EchoCommandOngoingMoreDataTemplate`
    - **Shellcode project**: `CommandEchoOngoingMoreData`

Additionally, there is a set of .NET utility classes that facilitate communication between the command shellcode and the agent. These are located at `shellcodes/tuoni-execunit-utils-dotnet/ExecUnitUtils` and are implemented as a shared code project, which is referenced and used by the shellcode solution. These are also available at [tuoni-execunit-utils-dotnet](https://github.com/shell-dot/tuoni-execunit-utils-dotnet) repository.

Each plugin folder contains both the shellcode source code and the Java plugin source code. 
Build binaries for the shellcode can be found at `shellcodes/CommandExecUnits/{command project}/bin/Release/{command project}.shellcode` and after building the plugin, the server plugin JAR can be found at `plugins/echo-command-plugin/build/libs/tuoni-example-plugin-echo-command-0.0.1.jar`.


---

Happy coding!

For more information on the Tuoni C2 framework, visit the [official Tuoni GitHub repository](https://github.com/shell-dot/tuoni).
