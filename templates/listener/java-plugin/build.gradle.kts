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
  compileOnly("com.shelldot:tuoni-plugin-sdk:0.15.0")
}

tasks.compileJava {
  options.release = 21
}

tasks.jar {
  // TODO: Replace the plugin identity before distributing your plugin.
  // Set a unique, stable Plugin-Id and meaningful provider/name/description/URL;
  // the host uses these manifest entries to identify the installed plugin. Keep
  // Plugin-Version aligned with project.version and keep renamed Java packages
  // consistent with the META-INF/services provider entry. Identity changes must
  // not leave the generated artifact or documentation claiming the template ID.
  manifest {
    attributes(
        "Plugin-Id" to "example.listener.template",
        "Plugin-Version" to project.version.toString(),
        "Plugin-Provider" to "example",
        "Plugin-Name" to "Listener Plugin Template",
        "Plugin-Description" to "Idle listener plugin template",
        "Plugin-Url" to "https://example.com"
    )
  }
}

val managedArtifacts = mapOf(
    "../exec-code/win/bin/Release/dotnet-exe/listener-execunit-template.dotnet_exe" to "listener.dotnet_exe",
    "../exec-code/win/bin/Release/dotnet-dll/listener-execunit-template.dotnet_dll" to "listener.dotnet_dll",
    "../exec-code/win/bin/Release/dotnet-dll/listener-execunit-template.dotnet_dll_method" to "listener.dotnet_dll_method"
)

val execUnitFormatsCheck by tasks.registering(JavaExec::class) {
  dependsOn(tasks.testClasses)
  classpath = sourceSets.test.get().runtimeClasspath
  mainClass.set("com.example.tuoni.listener.ExecUnitFormatsCheck")
}

tasks.check { dependsOn(execUnitFormatsCheck) }

// This standalone check has a main method; it is not a JUnit test class.
tasks.test { exclude("**/ExecUnitFormatsCheck*.class") }

val windowsNativeArtifacts = listOf("listener.native32_dll", "listener.native64_dll")

tasks.processResources {
  from("../exec-code/win-native/build") {
    include(windowsNativeArtifacts)
  }
  managedArtifacts.forEach { (source, resource) ->
    from(source) { rename { resource } }
  }
  from("../exec-code/linux/build") {
    include("listener-linux.native64_so")
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
    val shellcode = file("src/main/resources/listener.shellcode")
    if (!shellcode.isFile || shellcode.length() == 0L) {
      throw GradleException("Missing or empty ${shellcode.path}; rebuild the Windows Release solution with its post-build event.")
    }
    val native = file("../exec-code/linux/build/listener-linux.native64_so")
    if (!native.isFile || native.length() == 0L) {
      throw GradleException("Missing or empty ${native.path}; run make build-linux first.")
    }
  }
}
