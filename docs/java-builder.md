# Java build configuration

Java builds use a shared image containing Gradle and the dependencies required by
the examples and templates. Docker caches additional dependencies between builds.

Docker Buildx is a host-side Docker CLI plugin required by these BuildKit builds;
it is separate from the Java dependency image. `make build` checks Docker access
and Buildx before pulling that image. A fresh Docker installation through
`https://tuoni.sh` installs `docker-buildx-plugin`, but its existing-Docker path
checks only Docker and Compose versions and can leave Buildx missing. Install
`docker-buildx-plugin` for Docker CE, or `docker-buildx` for Debian/Kali's
`docker.io` packages. When Docker needs sudo, `sudo docker buildx version` must
also succeed.

The image's build files and maintainer instructions are in
[`tools/java-builder/`](../tools/java-builder/README.md).

## Image and cache settings

The defaults are defined in `tools/docker/java-builder.mk` and copied into each
project's `scripts/docker/java-builder.mk`:

| Setting | Default |
| --- | --- |
| `BUILDER_IMAGE` | `ghcr.io/shell-dot/tuoni-java-builder:0.15.0` |
| `GRADLE_CACHE_ID` | `tuoni-gradle-9.8.2-v3` |

Use `make build BUILDER_IMAGE=...` to select a custom Java image. Docker builds
target `linux/amd64`; ARM hosts require Docker's amd64 emulation.

## Cache lifetime

The Gradle cache belongs to the selected Docker builder. Projects using the same
cache ID share dependencies, with `sharing=locked` serializing Gradle access.
`make clean` removes project outputs and preserves this cache.

Docker pruning, garbage collection, or switching builders can discard downloaded
additions. A fresh cache starts with the dependencies included in the Java image;
missing libraries download during the next build.

New generated plugins include this configuration. To update an older generated
plugin, add the shared Make configuration and build flags, then update its Java
Docker stage to use the image and cache mount while preserving its selected native
resources.

## Transferring an image

Export a local image and load it on another machine:

```sh
docker save ghcr.io/shell-dot/tuoni-java-builder:0.15.0 -o java-builder.tar
docker load -i java-builder.tar
```

The archive contains the Java dependency baseline. Additional BuildKit cache
contents and native toolchain images are separate.

See Docker's [cache mounts](https://docs.docker.com/build/cache/optimize/#use-cache-mounts)
and Gradle's [dependency caching](https://docs.gradle.org/current/userguide/dependency_caching.html)
for the underlying behavior.
