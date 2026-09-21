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
  // Tuoni SDK must be included as compile dependency
  // The SDK is provided by the Tuoni server
  compileOnly(libs.tuoni.sdk)
  // All other dependencies should be included as runtime dependencies
  implementation(libs.jackson.databind)
}

// Tuoni plugins support Java 21+
java {
  sourceCompatibility = JavaVersion.VERSION_21
  targetCompatibility = JavaVersion.VERSION_21
}

tasks {
  jar { archiveClassifier = "shallow" }

  // Tuoni server requires the plugin to have all of its dependencies in a single JAR file
  shadowJar {
    archiveBaseName = "tuoni-example-plugin-dotnet-payload"
    archiveClassifier = ""

    manifest {
      // Add the required attributes for the Tuoni plugin
      attributes(
          mapOf(
              "Plugin-Id" to "shelldot.payloads.examples.dotnetpayload",
              "Plugin-Version" to project.version.toString(),
              "Plugin-Provider" to "shelldot",
              "Plugin-Name" to ".NET Payload Plugin",
              "Plugin-Description" to
                  "An example plugin with .NET payload.",
              "Plugin-Url" to "https://docs.shelldot.com",
          ))
    }
  }
  assemble { dependsOn(shadowJar) }
}

// Copy the agent executable template to the jar
tasks.processResources {
  from("../exec-code/bin/Release") {
    include("dotnet-agent.exe")
    into("templates/")
  }
}
