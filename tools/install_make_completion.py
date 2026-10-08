"""Install this repository's Make completion for the user's Bash or Zsh shell."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shlex
import tempfile


SOURCE = Path(__file__).with_name("make-completion.bash")
ZSH_SOURCE = Path(__file__).with_name("make-completion.zsh")
MARKER = b"# Tuoni make argument completion."
RC_BEGIN = "# >>> Tuoni Make completion >>>"
RC_END = "# <<< Tuoni Make completion <<<"


def install(destination: Path | None = None, *, shell: str = "bash") -> Path:
    if shell not in ("bash", "zsh"):
        raise ValueError(f"Unsupported completion shell: {shell}")
    source = ZSH_SOURCE if shell == "zsh" else SOURCE
    if destination is None:
        data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        destination = data_home / ("zsh/tuoni-make-completion.zsh" if shell == "zsh" else "bash-completion/completions/make")
    destination = destination.expanduser().absolute()
    if destination.exists() and not destination.read_bytes().startswith(MARKER):
        raise FileExistsError(f"Preserving existing completion: {destination}; source {source} instead")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary.write(source.read_bytes())
        staged = Path(temporary.name)
    try:
        staged.chmod(0o644)
        staged.replace(destination)
    finally:
        staged.unlink(missing_ok=True)
    return destination


def configure_zsh(destination: Path) -> Path:
    """Keep a single guarded source block, preserving the rest of .zshrc."""
    rc = (Path(os.environ.get("ZDOTDIR") or Path.home()) / ".zshrc").resolve()
    existing = rc.read_text() if rc.exists() else ""
    quoted = shlex.quote(str(destination))
    block = f"{RC_BEGIN}\nif [[ -r {quoted} ]]; then\n    source {quoted}\nfi\n{RC_END}\n"
    pattern = re.compile(rf"(?m)^{re.escape(RC_BEGIN)}\n.*?^{re.escape(RC_END)}\n?", re.DOTALL)
    matches = list(pattern.finditer(existing))
    if matches:
        updated = pattern.sub(lambda _: block, existing, count=1)
    elif RC_BEGIN in existing or RC_END in existing:
        raise OSError(f"Preserving incomplete Tuoni completion block in {rc}; source {destination} manually")
    else:
        updated = existing + ("\n" if existing and not existing.endswith("\n") else "") + block
    if updated != existing:
        rc.parent.mkdir(parents=True, exist_ok=True)
        mode = rc.stat().st_mode & 0o777 if rc.exists() else 0o600
        with tempfile.NamedTemporaryFile(mode="w", dir=rc.parent, delete=False) as temporary:
            temporary.write(updated)
            staged = Path(temporary.name)
        try:
            staged.chmod(mode)
            staged.replace(rc)
        finally:
            staged.unlink(missing_ok=True)
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", choices=("bash", "zsh"),
                        default=Path(os.environ.get("SHELL", "/bin/bash")).name,
                        help="shell to configure (default: your login shell)")
    args = parser.parse_args()
    if args.shell not in ("bash", "zsh"):
        parser.error("use --shell bash or --shell zsh to select a supported shell")
    try:
        destination = install(shell=args.shell)
        if args.shell == "zsh":
            rc = configure_zsh(destination)
            print(f"Enabled automatic loading in {rc}")
    except OSError as error:
        print(f"error: {error}")
        return 1
    print(f"Installed {args.shell.capitalize()} Make completion: {destination}")
    if args.shell == "bash":
        print("Requires Bash 4.2+ with bash-completion enabled (macOS: Homebrew bash and bash-completion@2).")
    print(f"Open a new {args.shell.capitalize()} shell, or enable it in this shell with:")
    print(f"  source {shlex.quote(str(destination))}")
    print("Use Tab for option names, EXECUNITS/OS values, and FOLDER paths.")
    print("Separate multiple EXECUNITS or OS values with commas to avoid quoting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
