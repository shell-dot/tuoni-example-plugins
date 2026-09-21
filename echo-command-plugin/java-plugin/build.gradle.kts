version = "0.0.1"

plugins {
  java
  id("com.gradleup.shadow") version "9.2.2"
}

repositories {
  // Use Maven Central for resolving dependencies.
  mavenCentral()
}

dependencies {
  // Tuoni SDK must be included as compile dependency
  // The SDK is provided by the Tuoni server
  compileOnly(libs.tuoni.sdk)
  // All other dependencies should be included as runtime dependencies
  implementation(libs.jackson.databind)
}

tasks.test { useJUnitPlatform() }

java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }

tasks {
  jar { archiveClassifier = "shallow" }

  // Tuoni server requires the plugin to have all of its dependencies in a single JAR file
  shadowJar {
    archiveBaseName = "tuoni-example-plugin-echo-command"
    archiveClassifier = ""

    doFirst {
      manifest {
        // Add the required attributes for the Tuoni plugin
        attributes(
            mapOf(
                "Plugin-Id" to "shelldot.commands.examples.echo",
                "Plugin-Version" to project.version.toString(),
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

tasks.processResources {
  commandShellcodes.forEach { command ->
    val compiledShellcode =
        layout.projectDirectory.file("../exec-code/$command/bin/Release/$command.shellcode").asFile
    val bundledShellcode =
        layout.projectDirectory.file("src/main/resources/shellcode/$command.shellcode").asFile

    from(providers.provider { if (compiledShellcode.isFile) compiledShellcode else bundledShellcode }) {
      into("shellcode/")
    }
  }
}
