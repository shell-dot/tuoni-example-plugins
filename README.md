# Tuoni Plugin Examples

Welcome to the Tuoni Plugin Examples repository! 

This repository contains example plugins for the [Tuoni](https://github.com/shell-dot/tuoni) Command and Control (C2) framework. \
Each plugin consists of two parts:

1. **Shellcode**: Written in C# and .NET.
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

1. **Echo Command Plugin**
    - **Shellcode**: `shellcodes/CommandEcho/`
    - **Server Plugin**: `plugins/echo-command-plugin/`

Each plugin folder contains both the shellcode source code and the Java plugin source code. 
Build binaries for the shellcode can be found at 
`shellcodes/CommandEcho/bin/Release/CommandEcho.shellcode` 
and after building the plugin, the server plugin JAR can be found at 
`plugins/echo-command-plugin/build/libs/tuoni-example-plugin-echo-command-0.0.1.jar`.


---

Happy coding!

For more information on the Tuoni C2 framework, visit the [official Tuoni GitHub repository](https://github.com/shell-dot/tuoni).
