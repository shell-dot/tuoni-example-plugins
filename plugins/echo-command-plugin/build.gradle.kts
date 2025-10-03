version = "0.0.1"

plugins {
  java
  id("com.github.johnrengelman.shadow") version "8.1.1"
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

// Copy the shellcode to the jar
tasks.processResources {
  from("../../shellcodes/CommandEcho/bin/Release") {
    include("CommandEcho.shellcode")
    into("shellcode/")
  }
}
