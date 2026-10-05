version = "0.0.1"

plugins {
  java
  id("com.gradleup.shadow") version "9.6.1"
}

repositories {
  mavenCentral()
}

dependencies {
  testImplementation("com.shelldot:tuoni-plugin-sdk:0.15.0")
  compileOnly(libs.tuoni.sdk)
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

  shadowJar {
    archiveBaseName = "tuoni-example-plugin-tcp-listener"
    archiveClassifier = ""

    val pluginVersion = project.version.toString()

    doFirst {
      manifest {
        attributes(
            mapOf(
                "Plugin-Id" to "shelldot.listener.examples.tcp",
                "Plugin-Version" to pluginVersion,
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

val execUnitFormatsCheck by tasks.registering(JavaExec::class) {
  dependsOn(tasks.testClasses)
  classpath = sourceSets.test.get().runtimeClasspath
  mainClass.set("com.shelldot.tuoni.examples.plugin.tcplistener.ExecUnitFormatsCheck")
}

tasks.check { dependsOn(execUnitFormatsCheck) }

// This standalone check has a main method; it is not a JUnit test class.
tasks.test { exclude("**/ExecUnitFormatsCheck*.class") }

val windowsNativeArtifacts = listOf("tcp-listener.native32_dll", "tcp-listener.native64_dll")

tasks.processResources {
  from("../exec-code/win-native/build") {
    include(windowsNativeArtifacts)
    into("shellcodes/")
  }
  from("../exec-code/win/tcp-listener/bin/Release/dotnet-exe") {
    include("tcp-listener.dotnet_exe")
    into("shellcodes/")
  }
  from("../exec-code/win/tcp-listener/bin/Release/dotnet-dll") {
    include("tcp-listener.dotnet_dll", "tcp-listener.dotnet_dll_method")
    into("shellcodes/")
  }
  from("../exec-code/win/tcp-listener/bin/Release") {
    include("tcp-listener.shellcode")
    into("shellcodes/")
  }
  from("../exec-code/linux/build") {
    include("tcp-listener-linux.native64_so")
    into("shellcodes/")
  }
  doFirst {
    windowsNativeArtifacts.forEach { name ->
      val artifact = file("../exec-code/win-native/build/$name")
      if (!artifact.isFile || artifact.length() == 0L) {
        throw GradleException("Missing or empty ${artifact.path}; run make build-windows-native first.")
      }
    }
    mapOf("dotnet-exe" to listOf("dotnet_exe"),
        "dotnet-dll" to listOf("dotnet_dll", "dotnet_dll_method")).forEach { (format, suffixes) ->
      suffixes.forEach { suffix ->
        val artifact = file("../exec-code/win/tcp-listener/bin/Release/$format/tcp-listener.$suffix")
        if (!artifact.isFile || artifact.length() == 0L) {
          throw GradleException("Missing or empty ${artifact.path}; build the managed ExecUnitFormat variants first.")
        }
      }
    }
    val shellcode = file("../exec-code/win/tcp-listener/bin/Release/tcp-listener.shellcode")
    if (!shellcode.exists()) {
      throw GradleException(
          "Missing shellcode at ${shellcode.path}. Build the .NET exec unit (Release) first " +
              "so that the donut post-build step produces tcp-listener.shellcode.")
    }
    val native = file("../exec-code/linux/build/tcp-listener-linux.native64_so")
    if (!native.isFile) {
      throw GradleException("Missing ${native.path}; run make build-linux first.")
    }
  }
}
