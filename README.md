# Tuoni Plugin Examples

Welcome to the Tuoni Plugin Examples repository!

This repository contains example plugins for the [Tuoni](https://github.com/shell-dot/tuoni) Command and Control (C2) framework. \
Each plugin consists of two parts:

1. **Execution codes and agent executables**: Written in C# .NET framework (`exec-code/`).
2. **Server Plugin** (`java-plugin/`): Written in Java against the Tuoni plugin SDK, requiring Java 21 and Gradle for building.

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

Each plugin's server part can be built using Gradle. Navigate to the individual plugin's `java-plugin/` directory and run the following command:
```
./gradlew assemble
```
This command will compile the Java code and build the server plugin.
Build the C# component first where required; see each plugin's README for its build order.

## Plugins

Here is a list of the example plugins included in this repository:

* **[Echo Command Plugin](echo-command-plugin/README.md) (contains 4 commands)**
  - **Server Plugin**: `echo-command-plugin/java-plugin/`
  - **Execution code**: `echo-command-plugin/exec-code/`

* **[TCP Listener Plugin](tcp-listener-plugin/README.md)**
  - **Server Plugin**: `tcp-listener-plugin/java-plugin/`
  - **Execution code**: `tcp-listener-plugin/exec-code/`

* **[.NET Payload Plugin](dotnet-payload-plugin/README.md)**
  - **Server Plugin**: `dotnet-payload-plugin/java-plugin/`
  - **Execution code**: `dotnet-payload-plugin/exec-code/`

---

Happy coding!

For more information on the Tuoni C2 framework, visit the [official Tuoni GitHub repository](https://github.com/shell-dot/tuoni).
