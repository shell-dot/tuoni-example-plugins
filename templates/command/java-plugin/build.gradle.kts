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
        "Plugin-Id" to "example.command.template",
        "Plugin-Version" to project.version.toString(),
        "Plugin-Provider" to "example",
        "Plugin-Name" to "Command Plugin Template",
        "Plugin-Description" to "Unimplemented command plugin skeleton",
        "Plugin-Url" to "https://example.com"
    )
  }
}

