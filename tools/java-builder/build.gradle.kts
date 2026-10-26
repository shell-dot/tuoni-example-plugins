plugins {
    java
    id("com.gradleup.shadow") version "9.6.1"
}

repositories {
    mavenCentral()
}

// Resolve separately so Gradle keeps both SDK versions instead of selecting the newer one.
val sdk017 = configurations.create("sdk017") {
    isCanBeConsumed = false
    isCanBeResolved = true
}

// This project has no application code; these declarations define the image's baseline.
dependencies {
    compileOnly("com.shelldot:tuoni-plugin-sdk:0.15.0")
    implementation("tools.jackson.core:jackson-databind:3.2.4")
    testImplementation("com.shelldot:tuoni-plugin-sdk:0.15.0")
    add(sdk017.name, "com.shelldot:tuoni-plugin-sdk:0.17.0")
}

tasks.register("resolveDependencies") {
    doLast {
        // Resolve actual files, including transitives, tests and annotation processors.
        configurations.filter { it.isCanBeResolved }.forEach { it.resolve() }
    }
}
