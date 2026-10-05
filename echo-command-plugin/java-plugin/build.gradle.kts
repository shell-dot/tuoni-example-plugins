version = "0.0.1"

plugins {
  java
  id("com.gradleup.shadow") version "9.6.1"
}

repositories {
  // Use Maven Central for resolving dependencies.
  mavenCentral()
}

dependencies {
  testImplementation("com.shelldot:tuoni-plugin-sdk:0.15.0")
  // Tuoni SDK must be included as compile dependency
  // The SDK is provided by the Tuoni server
  compileOnly(libs.tuoni.sdk)
  // All other dependencies should be included as runtime dependencies
  implementation(libs.jackson.databind)
}

tasks.test { useJUnitPlatform() }

// Tuoni plugins support Java 21+
java {
  sourceCompatibility = JavaVersion.VERSION_21
  targetCompatibility = JavaVersion.VERSION_21
}

tasks {
  jar { archiveClassifier = "shallow" }

  // Tuoni server requires the plugin to have all of its dependencies in a single JAR file
  shadowJar {
    archiveBaseName = "tuoni-example-plugin-echo-command"
    archiveClassifier = ""

    val pluginVersion = project.version.toString()

    doFirst {
      manifest {
        // Add the required attributes for the Tuoni plugin
        attributes(
            mapOf(
                "Plugin-Id" to "shelldot.commands.examples.echo",
                "Plugin-Version" to pluginVersion,
                "Plugin-Provider" to "shelldot",
                "Plugin-Name" to "Echo Command Example Plugin",
                "Plugin-Description" to
                    "An example plugin with an command template that echos back any input sent to it.",
                "Plugin-Url" to "https://docs.shelldot.com",
            ))
      }
    }
  }
  assemble { dependsOn(shadowJar) }
}

// Package rebuilt shellcode when available, otherwise use the bundled version of each command.
val commandShellcodes =
    listOf("echo", "echo-ongoing", "echo-ongoing-file", "echo-ongoing-more-data")

sourceSets {
  main {
    resources.exclude(commandShellcodes.map { "shellcode/$it.shellcode" })
  }
}

val execUnitFormatsCheck by tasks.registering(JavaExec::class) {
  dependsOn(tasks.testClasses)
  classpath = sourceSets.test.get().runtimeClasspath
  mainClass.set("com.shelldot.tuoni.examples.plugin.echo.ExecUnitFormatsCheck")
}

tasks.check { dependsOn(execUnitFormatsCheck) }

// This standalone check has a main method; it is not a JUnit test class.
tasks.test { exclude("**/ExecUnitFormatsCheck*.class") }

val windowsNativeArtifacts = listOf("echo.native32_dll", "echo.native64_dll", "echo-ongoing.native32_dll", "echo-ongoing.native64_dll", "echo-ongoing-file.native32_dll", "echo-ongoing-file.native64_dll", "echo-ongoing-more-data.native32_dll", "echo-ongoing-more-data.native64_dll")

tasks.processResources {
  from("../exec-code/win-native/build") {
    include(windowsNativeArtifacts)
    into("shellcode/")
  }
  commandShellcodes.forEach { command ->
    from("../exec-code/win/$command/bin/Release/dotnet-exe") {
      include("$command.dotnet_exe")
      into("shellcode/")
    }
    from("../exec-code/win/$command/bin/Release/dotnet-dll") {
      include("$command.dotnet_dll", "$command.dotnet_dll_method")
      into("shellcode/")
    }
    val compiledShellcode =
        layout.projectDirectory.file("../exec-code/win/$command/bin/Release/$command.shellcode").asFile
    val bundledShellcode =
        layout.projectDirectory.file("src/main/resources/shellcode/$command.shellcode").asFile

    from(providers.provider { if (compiledShellcode.isFile) compiledShellcode else bundledShellcode }) {
      into("shellcode/")
    }
    from("../exec-code/linux/build/${command}-linux.native64_so") {
      into("shellcode/")
    }
  }
  doFirst {
    windowsNativeArtifacts.forEach { name ->
      val artifact = file("../exec-code/win-native/build/$name")
      if (!artifact.isFile || artifact.length() == 0L) {
        throw GradleException("Missing or empty ${artifact.path}; run make build-windows-native first.")
      }
    }
    commandShellcodes.forEach { command ->
      mapOf("dotnet-exe" to listOf("dotnet_exe"),
          "dotnet-dll" to listOf("dotnet_dll", "dotnet_dll_method")).forEach { (format, suffixes) ->
        suffixes.forEach { suffix ->
          val artifact = file("../exec-code/win/$command/bin/Release/$format/$command.$suffix")
          if (!artifact.isFile || artifact.length() == 0L) {
            throw GradleException("Missing or empty ${artifact.path}; build the managed ExecUnitFormat variants first.")
          }
        }
      }
      val native = file("../exec-code/linux/build/${command}-linux.native64_so")
      if (!native.isFile) {
        throw GradleException("Missing ${native.path}; run make build-linux first.")
      }
    }
  }
}
