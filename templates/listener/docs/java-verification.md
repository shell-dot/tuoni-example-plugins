# Verify the Java plugin that will be shipped

Apply these checks after Java source, dependency, resource, service-registration or packaging changes. The full Docker build remains required. Compilation and ordinary Gradle tests can pass even when the delivered JAR cannot initialize because their classpaths contain libraries missing from that JAR.

## Check APIs and dependency ownership first

Read the actual SDK version and Java release in `java-plugin/build.gradle.kts`. Inspect SDK signatures with the [build guide](building.md#inspect-sdk-signatures-before-adding-hooks), use `@Override`, and verify constructors, return types and declared exceptions before adding hooks. Do not copy server-internal helpers or invent SDK methods. Keep fixed metadata/schema strings simple; do not introduce a JSON library just to return fixed JSON. Dynamic parsing still needs a real parser and typed validation, not hand-written string splitting.

For every non-JDK import, identify its artifact/version and owner: a verified host API or a plugin-owned runtime dependency. Account for transitive classes and resources as well as direct imports. Keep the SDK `compileOnly`; retain the actual host contracts for PF4J/SLF4J rather than bundling or relocating copies. The SDK does not supply a JSON parser.

## Respect the plugin loader boundary

The reviewed Tuoni `CustomPluginClassLoader` delegates `org.pf4j.*`, `org.slf4j.*` and `com.shelldot.tuoni.plugin.sdk.*` to its parent; `java.*` uses the system loader. Other packages are looked up in the plugin artifact, with only a bootstrap-loaded class accepted as fallback. Resources are looked up in the plugin too. Check the actual deployed loader/version when testing compatibility; the optional source checkout is located via [existing plugin references](existing-plugins.md).

Therefore Jackson on the server classpath is not available to this plugin. `NoClassDefFoundError: tools/jackson/core/JacksonException` during provider/template creation means that runtime path could not resolve the required class; inspect the delivered artifact and loader policy before changing Java behavior. Do not solve it by copying libraries into the server, disabling validation, returning an empty template list, or catching `LinkageError` as an invalid user configuration.

Use the [dependency packaging recipe](building.md#java-dependencies-and-compilation):

- `implementation` and `runtimeOnly` make dependencies available to Gradle but a plain `jar` does not bundle them. For a single-JAR distribution, merge the plugin-owned runtime dependency closure, including required service/reflection resources, into the distributable.
- Shadow bundles `runtimeClasspath` by default. Dependencies placed only in its `shadow` configuration remain external. Avoid exclusions or `minimize()` unless the isolated checks below prove all reflective/service-loaded paths still work. See [Shadow dependency handling](https://gradleup.com/shadow/configuration/dependencies/) and [runtime classpath configuration](https://gradleup.com/shadow/configuration/).
- Match imports to the selected library major version. Jackson 3 core/databind use `tools.jackson.*`; its annotations still use `com.fasterxml.jackson.annotation.*`. Bundling Jackson 2 core does not satisfy a Jackson 3 import. Use resolved compatible versions, following the [Jackson migration notes](https://github.com/FasterXML/jackson/blob/main/jackson3/MIGRATING_TO_JACKSON_3.md).
- Preserve the SDK service descriptor and every required `Plugin-*` manifest value. Keep Gradle's distributable filename, Make's `JAR_NAME`, and the Docker artifact `COPY` aligned. A successful `shadowJar` task is irrelevant if Docker exports the thin or `-shallow` JAR instead.
- Dependencies must be at paths the loader can load. Placing dependency JARs inside the plugin JAR is not equivalent to unpacked dependency classes. Do not add relocation merely to work around this error; if relocation is already used, verify rewritten classes/resources and the actual runtime call path together.

## Verify the exported artifact

Use the exact JAR exported by the full Docker build and intended for delivery. Do not choose the first wildcard match under `build/libs`. Run the copied [archive checker](../scripts/verify_java_artifact.py) from the plugin root (the example below is for a plugin using Jackson 3):

```sh
python scripts/verify_java_artifact.py build/listener-plugin-template-0.0.1.jar --kind listener --jackson3
```

Use `--jackson3` only when the plugin uses Jackson 3. Otherwise omit it and use repeated `--require-class fully.qualified.Name` arguments for its actual private libraries. The Jackson check includes all four sentinels:

- `tools/jackson/databind/json/JsonMapper.class`
- `tools/jackson/core/JsonParser.class`
- `tools/jackson/core/JacksonException.class`
- `com/fasterxml/jackson/annotation/JsonProperty.class`

The checker validates archive structure, nonempty manifest metadata, provider class entries, required class entries and absence of bundled SDK classes. Also compare manifest identity/provider values with the intended plugin and compare native resource bytes with the fresh outputs as described in [Package and verify](building.md#package-and-verify). Record the JAR path and SHA-256. These presence checks do not prove a complete dependency closure, compatible bytecode, or successful initialization; continue with the runtime check below.

## Isolated initialization smoke test

Create or update a small, plugin-specific startup fixture and run it in a **fresh JVM in Docker**, using the project Java target and the exact exported JAR. Make it a repeatable check for later changes. When wired into Gradle/Docker verification, make failure fail the verification task and propagate a nonzero process result; keep the full build/export requirement intact.

1. Use the compatible Tuoni loader when available, or a focused loader that faithfully enforces the reviewed package/resource boundary. Its plugin lookup must contain only the delivered JAR. Parent access is restricted to JDK and the verified host contracts; no Jackson or other plugin-owned dependency may be rescued from a parent loader. A normal parent-first `URLClassLoader` on a broad test classpath is insufficient.
2. Keep the harness separate from plugin code. Do not add `sourceSets.main.output`, `sourceSets.test.runtimeClasspath`, the plugin's Gradle `runtimeClasspath`, IDE libraries, exploded main classes or the server's entire library folder to the runtime classpath. The host-contract side can contain the matching SDK and its actual required host APIs; it must not supply plugin-private classes. Use the plugin loader explicitly for SPI discovery and the thread context loader where required, restoring the previous context afterward.
3. Instantiate every expected provider from this JAR's actual `META-INF/services` descriptor, confirming its class comes from that JAR. This must trigger constructors/static initializers. Exercise the startup sequence below with faithful, minimal SDK contexts. Do not pass `null` and then swallow the resulting exceptions or skip calls. Unexpected context calls should fail the fixture so its setup can be corrected.

For listeners, mirror the reviewed host order: read `getExampleConfigurations()` and `getConfigurationSchema()` **before** `init(ListenerPluginContext)`, then call `initializeGlobalCommandTemplates(CommandPluginContext)` and inspect all returned templates. Metadata must not require initialized context. Force schema `jsonSchema()`/`fileSchemas()` and serialization of JSON or multipart JSON examples. For any global templates, exercise their metadata/schema/example methods just as the host does. Use current SDK signatures; do not add command-style `parseResult` hooks to listeners.

4. Exercise at least one valid configuration through the actual factory and one invalid configuration through its real validation path. A no-fields schema must accept `{}`. Parse schema/example JSON and verify defaults, schema/example agreement, and expected SDK validation exceptions. Assert expected template/provider counts, unique names and required nonnull metadata so empty fallback collections cannot hide a failed registration. Force lazy dependencies in the affected Java paths: configuration generation for supported platform metadata, changed output parsing or transport decoding, and cleanup of Java-owned resources. Do not execute native code just to test Java resource selection/encoding. A server-facing network lifecycle requires its own controlled fixture if changed.
5. Prove that the isolation check can detect missing private dependencies: when adding/changing a library or the harness, use a disposable copy with one required private class removed (for this regression, `JacksonException.class`) and require initialization to fail for that missing class or its dependent linkage. An unrelated fixture/context failure does not validate isolation. Do not modify the delivery artifact. Recheck that the intact artifact passes. A test that still passes the broken copy is using the wrong classpath, artifact or startup path.
6. Preserve the full cause chain and fail on provider discovery errors, linkage errors, missing resources and unexpected initialization exceptions. Release fixture contexts/resources and close the loader afterward. Do not mark a swallowed exception, empty provider list or skipped initialization as success.

A faithful isolated test verifies the exercised startup/factory paths. Record an actual Tuoni integration test separately when available; do not imply a simulation covered a different deployed loader. If Docker, required host APIs or a compatible loader fixture are unavailable, report the exact blocked check and continue independent work; no automatic local-build fallback. A JAR that failed initialization is not ready to deliver even when compilation passed.

## Evidence before finishing

Record the exact exported JAR path/hash, SDK/Java/loader versions, full Docker build result, archive-check command/result, isolated startup/factory fixture command/result and any missing-dependency regression. Keep native payload/lifecycle tests separate. After dependency, source or export changes, rebuild and rerun the checks against the new JAR. An old successful test, a thin JAR, or tests against compiled source directories do not verify the delivered plugin.
