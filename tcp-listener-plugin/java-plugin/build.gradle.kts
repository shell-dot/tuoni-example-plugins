version = "0.0.1"

plugins {
  java
  id("com.gradleup.shadow") version "9.2.2"
}

repositories {
  mavenCentral()
}

dependencies {
  compileOnly(libs.tuoni.sdk)
  implementation(libs.jackson.databind)
}

tasks.test { useJUnitPlatform() }

java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }

tasks {
  jar { archiveClassifier = "shallow" }

  shadowJar {
    archiveBaseName = "tuoni-example-plugin-tcp-listener"
    archiveClassifier = ""

    doFirst {
      manifest {
        attributes(
            mapOf(
                "Plugin-Id" to "shelldot.listener.examples.tcp",
                "Plugin-Version" to project.version.toString(),
                "Plugin-Provider" to "shelldot",
                "Plugin-Name" to "TCP Listener Plugin",
                "Plugin-Description" to "An example TCP listener plugin",
                "Plugin-Url" to "https://docs.shelldot.com",
            ))
      }
    }
  }

  assemble { dependsOn(shadowJar) }
}

tasks.processResources {
  from("../exec-code/tcp-listener/bin/Release") {
    include("tcp-listener.shellcode")
    into("shellcodes/")
  }
  doFirst {
    val shellcode = file("../exec-code/tcp-listener/bin/Release/tcp-listener.shellcode")
    if (!shellcode.exists()) {
      throw GradleException(
          "Missing shellcode at ${shellcode.path}. Build the .NET exec unit (Release) first " +
              "so that the donut post-build step produces tcp-listener.shellcode.")
    }
  }
}
