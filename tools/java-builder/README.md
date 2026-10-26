# Tuoni Java builder

Builds `ghcr.io/shell-dot/tuoni-java-builder:0.15.0` with Java 21, Gradle 9.7.1,
Tuoni SDKs 0.15.0 and 0.17.0, Jackson 3.2.2 and the Shadow 9.6.1 plugin.
Gradle resolves their transitive dependencies into `/opt/gradle-home`.

This directory contains its own build configuration, Gradle wrapper and dependency
project. Its Docker build context is limited to this directory and has no
dependencies on the examples or templates.

## Build and check

With Docker and GNU Make available, run from the repository root:

```sh
make -C tools/java-builder build
make -C tools/java-builder check
```

`make build` creates the image locally and reports its size. `make check` resolves
the declared dependencies inside that image with networking disabled. Neither
command publishes anything. Use `DOCKER='sudo docker'` if required by your setup,
or `BUILDER_IMAGE=...` to choose another tag. ARM hosts require amd64 emulation.

The empty Gradle project in `build.gradle.kts` is the dependency source. Add or
update baseline libraries there, then rebuild and check the image. The wrapper
configuration pins Gradle and its distribution checksum. The Dockerfile pins the
Java major version. No host dependency cache is imported into the image.

## Publishing

The [GitHub Actions workflow](../../.github/workflows/java-builder.yml) runs only
through manual dispatch. It builds the image and verifies its dependencies.
`publish` defaults to `false`. Enabling it transfers the validated image to a
separate publishing job with package-write access. The build job has read-only
repository access, and checkout does not retain its credentials.

When releasing a new baseline, coordinate the image tag with
`tools/docker/java-builder.mk` and its copies in the examples and templates.
Advance `GRADLE_CACHE_ID` so new caches use the new seed.
