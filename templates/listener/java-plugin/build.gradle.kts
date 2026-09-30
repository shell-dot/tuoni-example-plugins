plugins {
  java
}

group = "com.example.tuoni"
version = "0.0.1"

repositories {
  mavenCentral()
}

dependencies {
  // Match the SDK used by the examples. Tuoni supplies it at runtime.
  compileOnly("com.shelldot:tuoni-plugin-sdk:0.15.0")
}

tasks.compileJava {
  options.release = 21
}

tasks.jar {
  // TODO: Replace the plugin identity before distributing your plugin.
  manifest {
    attributes(
        "Plugin-Id" to "example.listener.template",
        "Plugin-Version" to project.version.toString(),
        "Plugin-Provider" to "example",
        "Plugin-Name" to "Listener Plugin Template",
        "Plugin-Description" to "Unimplemented listener plugin skeleton",
        "Plugin-Url" to "https://example.com"
    )
  }
}

tasks.processResources {
  from("../exec-code/linux/build") {
    include("listener-linux.native64_so")
  }
  doFirst {
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
