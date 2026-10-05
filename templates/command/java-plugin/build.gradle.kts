plugins {
  java
}

group = "com.example.tuoni"
version = "0.0.1"

repositories {
  mavenCentral()
}

dependencies {
  testImplementation("com.shelldot:tuoni-plugin-sdk:0.15.0")
  // Match the SDK used by the examples. Tuoni supplies it at runtime.
  // Add any implementation-only parser/library dependencies explicitly and package
  // their runtime classes in the distributed plugin; compileOnly is appropriate for
  // the host-provided SDK, not a new private dependency. See docs/building.md.
  compileOnly("com.shelldot:tuoni-plugin-sdk:0.15.0")
}

tasks.compileJava {
  options.release = 21
}

tasks.jar {
  // TODO: Replace the plugin identity before distributing your plugin.
  // These manifest attributes identify the provider to Tuoni, independently of its
  // command name and Java package. Choose a unique stable Plugin-Id, keep the version
  // aligned with project.version, and supply the actual provider/name/description/URL.
  // Preserve the service-provider registration and native resource names when
  // renaming the scaffold, or update their Java/build consumers together.
  manifest {
    attributes(
        "Plugin-Id" to "example.command.template",
        "Plugin-Version" to project.version.toString(),
        "Plugin-Provider" to "example",
        "Plugin-Name" to "Command Plugin Template",
        "Plugin-Description" to "No-op command plugin template",
        "Plugin-Url" to "https://example.com"
    )
  }
}

val managedArtifacts = mapOf(
    "../exec-code/win/bin/Release/dotnet-exe/command-execunit-template.dotnet_exe" to "command.dotnet_exe",
    "../exec-code/win/bin/Release/dotnet-dll/command-execunit-template.dotnet_dll" to "command.dotnet_dll",
    "../exec-code/win/bin/Release/dotnet-dll/command-execunit-template.dotnet_dll_method" to "command.dotnet_dll_method"
)

val execUnitFormatsCheck by tasks.registering(JavaExec::class) {
  dependsOn(tasks.testClasses)
  classpath = sourceSets.test.get().runtimeClasspath
  mainClass.set("com.example.tuoni.command.ExecUnitFormatsCheck")
}

tasks.check { dependsOn(execUnitFormatsCheck) }

// This standalone check has a main method; it is not a JUnit test class.
tasks.test { exclude("**/ExecUnitFormatsCheck*.class") }

val windowsNativeArtifacts = listOf("command.native32_dll", "command.native64_dll")

tasks.processResources {
  from("../exec-code/win-native/build") {
    include(windowsNativeArtifacts)
  }
  managedArtifacts.forEach { (source, resource) ->
    from(source) { rename { resource } }
  }
  // Bundle rebuilt exec-unit artifacts at the exact classpath paths consumed by
  // TemplateCommand. Java compilation cannot establish that these bytes implement
  // the requested native behavior; keep every exec-unit build in the build workflow.
  from("../exec-code/linux/build") {
    include("command-linux.native64_so")
  }
  doFirst {
    windowsNativeArtifacts.forEach { name ->
      val artifact = file("../exec-code/win-native/build/$name")
      if (!artifact.isFile || artifact.length() == 0L) {
        throw GradleException("Missing or empty ${artifact.path}; run make build-windows-native first.")
      }
    }
    managedArtifacts.keys.forEach { source ->
      val artifact = file(source)
      if (!artifact.isFile || artifact.length() == 0L) {
        throw GradleException("Missing or empty ${artifact.path}; build both managed ExecUnitFormat variants first.")
      }
    }
    val shellcode = file("src/main/resources/command.shellcode")
    if (!shellcode.isFile || shellcode.length() == 0L) {
      throw GradleException("Missing or empty ${shellcode.path}; rebuild the Windows Release solution with its post-build event.")
    }
    val native = file("../exec-code/linux/build/command-linux.native64_so")
    if (!native.isFile || native.length() == 0L) {
      throw GradleException("Missing or empty ${native.path}; run make build-linux first.")
    }
  }
}
