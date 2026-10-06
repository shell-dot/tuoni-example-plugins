"""Render build files for a scaffold with a selected support matrix."""

from __future__ import annotations

import re
from pathlib import Path


def _stage(dockerfile: str, name: str) -> str:
    matches = list(re.finditer(r"(?m)^FROM [^\n]+ AS ([a-z-]+)\s*$", dockerfile))
    for index, match in enumerate(matches):
        if match.group(1) == name:
            end = matches[index + 1].start() if index + 1 < len(matches) else len(dockerfile)
            block = dockerfile[match.start():end].rstrip()
            return re.sub(r"\n(?:# [^\n]*\n?)+\Z", "", block).rstrip()
    raise ValueError(f"Missing Docker build stage: {name}")


def _dockerfile(root: Path, kind: str, slug: str, matrix: dict[str, set[str]]) -> None:
    path = root / "scripts/docker/Dockerfile"
    original = path.read_text(encoding="utf-8")
    windows = matrix.get("windows", set())
    linux_native = "native-lib" in matrix.get("linux", set())
    windows_native = "native-lib" in windows
    shellcode = "shellcode-native" in windows
    managed = {name for name in ("dotnet-exe", "dotnet-dll") if name in windows}
    artifact = f"{kind}-{slug}"
    executable = f"{artifact}-execunit"
    jar = f"{kind}-plugin-{slug}-0.0.1.jar"
    stages: list[str] = []

    if managed or shellcode:
        csharp = _stage(original, "csharp-build")
        formats = [
            name for name in ("shellcode", "dotnet-exe", "dotnet-dll")
            if name == "shellcode" and shellcode or name in managed
        ]
        old = "for format in shellcode dotnet-exe dotnet-dll; do"
        if csharp.count(old) != 1:
            raise ValueError("Unexpected managed build loop in scaffold Dockerfile")
        stages.append(csharp.replace(old, f"for format in {' '.join(formats)}; do"))
    if shellcode:
        stages.append(_stage(original, "shellcode-build"))
    if linux_native:
        stages.append(_stage(original, "linux-build"))
        stages.append(_stage(original, "linux-artifacts"))
    if windows_native:
        stages.append(_stage(original, "windows-native-build"))
        stages.append(_stage(original, "windows-native-artifacts"))

    java = ["FROM eclipse-temurin:21-jdk AS java-build",
            "WORKDIR /build", "COPY java-plugin/ java-plugin/"]
    if windows_native:
        java.append("COPY --from=windows-native-build /build/exec-code/win-native/build/ exec-code/win-native/build/")
    if managed:
        java.append("COPY --from=csharp-build /build/exec-code/win/ /build/exec-code/win/")
    if shellcode:
        java.append(
            f"COPY --from=shellcode-build /build/exec-code/win/bin/Release/{executable}.shellcode "
            f"/build/java-plugin/src/main/resources/{artifact}.shellcode"
        )
    if linux_native:
        java.append(
            f"COPY --from=linux-build /build/exec-code/linux/build/{artifact}-linux.native64_so "
            f"/build/exec-code/linux/build/{artifact}-linux.native64_so"
        )
    java.extend(("WORKDIR /build/java-plugin",
                 "RUN chmod +x gradlew && ./gradlew build --no-daemon"))
    stages.append("\n".join(java))

    if managed:
        dotnet = ["FROM scratch AS dotnet-artifacts"]
        if "dotnet-exe" in managed:
            dotnet.append(
                f"COPY --from=csharp-build /build/exec-code/win/bin/Release/dotnet-exe/{executable}.dotnet_exe "
                f"/{executable}.dotnet_exe"
            )
        if "dotnet-dll" in managed:
            for suffix in ("dotnet_dll", "dotnet_dll_method"):
                dotnet.append(
                    f"COPY --from=csharp-build /build/exec-code/win/bin/Release/dotnet-dll/{executable}.{suffix} "
                    f"/{executable}.{suffix}"
                )
        stages.append("\n".join(dotnet))

    exports = ["FROM scratch AS artifacts"]
    if windows_native:
        exports.append("COPY --from=windows-native-artifacts / /")
    if managed:
        exports.append("COPY --from=dotnet-artifacts / /")
    if shellcode:
        exports.append(
            f"COPY --from=shellcode-build /build/exec-code/win/bin/Release/{executable}.shellcode "
            f"/{executable}.shellcode"
        )
    if linux_native:
        exports.append(
            f"COPY --from=linux-build /build/exec-code/linux/build/{artifact}-linux.native64_so "
            f"/{artifact}-linux.native64_so"
        )
    exports.append(
        f"COPY --from=java-build /build/java-plugin/build/libs/{jar} /{jar}"
    )
    stages.append("\n".join(exports))
    path.write_text("\n\n".join(stages) + "\n", encoding="utf-8")


def _gradle(root: Path, kind: str, slug: str, package_part: str,
            matrix: dict[str, set[str]]) -> None:
    path = root / "java-plugin/build.gradle.kts"
    content = path.read_text(encoding="utf-8")
    head, marker, _ = content.partition("val managedArtifacts = mapOf(")
    if not marker:
        raise ValueError("Missing managed artifact section in scaffold Gradle file")
    windows = matrix.get("windows", set())
    linux_native = "native-lib" in matrix.get("linux", set())
    windows_native = "native-lib" in windows
    shellcode = "shellcode-native" in windows
    artifact = f"{kind}-{slug}"
    executable = f"{artifact}-execunit"
    managed_pairs = []
    if "dotnet-exe" in windows:
        managed_pairs.append(
            f'    "../exec-code/win/bin/Release/dotnet-exe/{executable}.dotnet_exe" to "{artifact}.dotnet_exe"'
        )
    if "dotnet-dll" in windows:
        managed_pairs.extend((
            f'    "../exec-code/win/bin/Release/dotnet-dll/{executable}.dotnet_dll" to "{artifact}.dotnet_dll"',
            f'    "../exec-code/win/bin/Release/dotnet-dll/{executable}.dotnet_dll_method" to "{artifact}.dotnet_dll_method"',
        ))
    lines = [
        "val managedArtifacts: Map<String, String> = mapOf(",
        ",\n".join(managed_pairs) if managed_pairs else "",
        ")",
        "",
        "val execUnitFormatsCheck by tasks.registering(JavaExec::class) {",
        "  dependsOn(tasks.testClasses)",
        "  classpath = sourceSets.test.get().runtimeClasspath",
        f'  mainClass.set("com.example.tuoni.{kind}.{package_part}.ExecUnitFormatsCheck")',
        "}",
        "",
        "tasks.check { dependsOn(execUnitFormatsCheck) }",
        'tasks.test { exclude("**/ExecUnitFormatsCheck*.class") }',
        "",
        "tasks.processResources {",
    ]
    if windows_native:
        lines.extend((
            '  from("../exec-code/win-native/build") {',
            f'    include("{artifact}.native32_dll", "{artifact}.native64_dll")',
            "  }",
        ))
    lines.extend((
        "  managedArtifacts.forEach { (source, resource) ->",
        "    from(source) { rename { resource } }",
        "  }",
    ))
    if linux_native:
        lines.extend((
            '  from("../exec-code/linux/build") {',
            f'    include("{artifact}-linux.native64_so")',
            "  }",
        ))
    lines.append("  doFirst {")
    if windows_native:
        lines.extend((
            f'    for (name in listOf("{artifact}.native32_dll", "{artifact}.native64_dll")) {{',
            '      val file = file("../exec-code/win-native/build/$name")',
            '      if (!file.isFile || file.length() == 0L) throw GradleException("Missing or empty $name")',
            "    }",
        ))
    lines.extend((
        "    managedArtifacts.keys.forEach { source ->",
        "      val file = file(source)",
        '      if (!file.isFile || file.length() == 0L) throw GradleException("Missing or empty $source")',
        "    }",
    ))
    if shellcode:
        lines.extend((
            f'    val shellcode = file("src/main/resources/{artifact}.shellcode")',
            '    if (!shellcode.isFile || shellcode.length() == 0L) throw GradleException("Missing or empty shellcode")',
        ))
    if linux_native:
        lines.extend((
            f'    val native = file("../exec-code/linux/build/{artifact}-linux.native64_so")',
            '    if (!native.isFile || native.length() == 0L) throw GradleException("Missing or empty Linux library")',
        ))
    lines.extend(("  }", "}"))
    path.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def _makefile(root: Path, kind: str, slug: str, matrix: dict[str, set[str]]) -> None:
    path = root / "Makefile"
    windows = matrix.get("windows", set())
    linux_native = "native-lib" in matrix.get("linux", set())
    windows_native = "native-lib" in windows
    managed = {name for name in ("dotnet-exe", "dotnet-dll") if name in windows}
    shellcode = "shellcode-native" in windows
    artifact = f"{kind}-{slug}"
    executable = f"{artifact}-execunit"
    jar = f"{kind}-plugin-{slug}-0.0.1.jar"
    all_outputs = [jar]
    managed_outputs = []
    if "dotnet-exe" in managed:
        managed_outputs.append(f"{executable}.dotnet_exe")
    if "dotnet-dll" in managed:
        managed_outputs.extend((f"{executable}.dotnet_dll", f"{executable}.dotnet_dll_method"))
    all_outputs.extend(managed_outputs)
    if shellcode:
        all_outputs.append(f"{executable}.shellcode")
    if linux_native:
        all_outputs.append(f"{artifact}-linux.native64_so")
    if windows_native:
        all_outputs.extend((f"{artifact}.native32_dll", f"{artifact}.native64_dll"))
    lines = [
        "#!make", ".DEFAULT_GOAL := help", "",
        "DOCKER ?= sh scripts/docker/run-docker.sh",
        "BUILD_DIR := build", "",
        ".PHONY: help build build-dotnet build-linux build-windows-native clean", "",
        "help:",
        "\t@printf '%s\\n' 'make build  Build selected execunits and the plugin JAR with Docker' "
        "'make build-dotnet  Export selected .NET formats' "
        "'make build-linux  Export the Linux native library' "
        "'make build-windows-native  Export Windows native DLLs' "
        "'make clean  Remove extracted build artifacts'",
        "",
    ]

    def docker_target(target: str, output: str) -> list[str]:
        return [
            '\t@mkdir -p -- "' + output + '"',
            "\tDOCKER_BUILDKIT=1 $(DOCKER) build \\",
            "\t\t-f scripts/docker/Dockerfile \\",
            f"\t\t--target {target} \\",
            '\t\t--output "type=local,dest=' + output + '/" \\',
            "\t\t.",
        ]

    lines.append("build:")
    lines.append("\t@$(MAKE) clean")
    lines.extend(docker_target("artifacts", "$(BUILD_DIR)"))
    lines.append("\t@printf '%s\\n' " + " ".join(f'"Built $(BUILD_DIR)/{name}"' for name in all_outputs))
    lines.append("")

    def unsupported(target: str) -> list[str]:
        return [f"{target}:", f"\t@printf '%s\\n' 'No {target} artifacts are selected.' >&2; exit 2", ""]

    if managed:
        lines.append("build-dotnet:")
        lines.extend(docker_target("dotnet-artifacts", "$(BUILD_DIR)"))
        lines.append("\t@printf '%s\\n' " + " ".join(f'"Built $(BUILD_DIR)/{name}"' for name in managed_outputs))
        lines.append("")
    else:
        lines.extend(unsupported("build-dotnet"))
    if linux_native:
        lines.append("build-linux:")
        lines.extend(docker_target("linux-artifacts", "exec-code/linux/build"))
        lines.append('\t@mkdir -p -- "$(BUILD_DIR)"')
        lines.append(f'\tcp exec-code/linux/build/{artifact}-linux.native64_so "$(BUILD_DIR)/"')
        lines.append("")
    else:
        lines.extend(unsupported("build-linux"))
    if windows_native:
        lines.append("build-windows-native:")
        lines.extend(docker_target("windows-native-artifacts", "exec-code/win-native/build"))
        lines.append('\t@mkdir -p -- "$(BUILD_DIR)"')
        lines.append('\tcp exec-code/win-native/build/*.native32_dll exec-code/win-native/build/*.native64_dll "$(BUILD_DIR)/"')
        lines.append("")
    else:
        lines.extend(unsupported("build-windows-native"))
    lines.extend((
        "clean:",
        "\t@set -eu; \\",
        "\tproject_dir=$$(pwd -P); \\",
        '\tfor candidate in "$(BUILD_DIR)" exec-code/linux/build exec-code/win-native/build; do \\',
        '\t\tif [ ! -d "$$candidate" ]; then continue; fi; \\',
        '\t\tartifact_dir=$$(CDPATH= cd -- "$$candidate" && pwd -P); \\',
        '\t\tif [ "$$artifact_dir" != "$$project_dir/$$candidate" ]; then printf "%s\\n" "Refusing to clean redirected build directory: $$candidate" >&2; exit 1; fi; \\',
        '\t\trm -rf -- "$$artifact_dir"; \\',
        "\tdone",
    ))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def configure_selected_build(root: Path, kind: str, slug: str, package_part: str,
                             matrix: dict[str, set[str]]) -> None:
    _dockerfile(root, kind, slug, matrix)
    _gradle(root, kind, slug, package_part, matrix)
    _makefile(root, kind, slug, matrix)
