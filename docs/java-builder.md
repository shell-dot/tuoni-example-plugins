# Java build configuration

Java builds use a shared image containing Gradle and the dependencies required by
the examples and templates. Docker caches additional dependencies between builds.

Docker Buildx is a host-side Docker CLI plugin required by these BuildKit builds;
it is separate from the Java dependency image. `make build` checks Docker access
and Buildx before pulling that image. A fresh Docker installation through
`https://tuoni.sh` installs `docker-buildx-plugin`, but its existing-Docker path
checks only Docker and Compose versions and can leave Buildx missing.

When Buildx is missing on Debian, Kali, Ubuntu or a derivative, the standalone
`scripts/docker/check-buildx.sh` helper reads `/etc/os-release` and checks which
package owns the resolved Docker CLI executable. Docker CE (`docker-ce-cli`) uses
`docker-buildx-plugin`; distro `docker.io` uses `docker-buildx`. Either installation
can be used on Kali, so the OS name alone does not select a package. See the
[Docker CE installation instructions](https://docs.docker.com/engine/install/debian/)
and [Kali package listing](https://pkg.kali.org/pkg/docker-buildx).

The helper prints the detected environment and exact commands, then asks
`Install <package> now and continue the build? [y/N]`. Approval runs `apt-get update`
and `apt-get install -y --no-remove <package>`, through sudo when needed. It uses
existing repositories and refuses package removals. It verifies Buildx through
the same Docker launcher or `DOCKER=...` override before continuing.

Without terminal input the build stops with installation instructions. Use
`make build BUILDX_INSTALL=1` to explicitly allow installation without prompting;
`make build BUILDX_INSTALL=0` disables the offer. Existing Buildx installations
skip all detection and package operations. Unknown Docker package sources and
unsupported operating systems receive manual setup guidance. Apt/sudo failures
stop the build; the helper does not replace Docker or configure repositories.
When Docker needs sudo, `sudo docker buildx version` must also succeed.

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

For a plugin that already uses the shared Java image, copy
`scripts/docker/check-buildx.sh` and `scripts/docker/java-builder.mk` from the
matching template to add the installation offer, preserving any custom defaults.
Generated workspaces retain their copied build files when this repository updates.

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
