#!/usr/bin/env python3
"""Interactive command/listener scaffolding using only Python's standard library."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import shlex
import sys
import textwrap
import unicodedata
from typing import Optional

try:
    import curses
except ImportError:
    curses = None

import scaffold_plugin as scaffold


KINDS = ("command", "listener")
STEPS = ("Type", "Name", "Platforms", "Formats", "Destination", "Review")
FORMAT_LABELS = {
    "shellcode-native": "Native shellcode (Windows)",
    "dotnet-dll": ".NET DLL (Windows)",
    "dotnet-exe": ".NET executable (Windows)",
    "native-lib": "Native library (Windows DLL / Linux .so)",
}
EXPECTED_ERRORS = (OSError, ValueError, RuntimeError)


@dataclass
class PluginPlan:
    kind: str = "command"
    name: str = ""
    folder: str = ""
    systems: set[str] = field(default_factory=lambda: set(scaffold.OPERATING_SYSTEMS))
    formats: set[str] = field(default_factory=lambda: set(scaffold.EXECUNITS))

    @property
    def slug(self) -> str:
        return "-".join(scaffold.name_parts(self.name))

    @property
    def available_formats(self) -> tuple[str, ...]:
        available = set().union(*(scaffold.AVAILABLE_FORMATS[os_name] for os_name in self.systems))
        return tuple(value for value in scaffold.EXECUNITS if value in available)

    def selection_arguments(self) -> tuple[Optional[str], Optional[str]]:
        formats = self.formats.intersection(self.available_formats)
        # Keep an untouched selection identical to the existing Make defaults.
        if formats == set(scaffold.EXECUNITS) and self.systems == set(scaffold.OPERATING_SYSTEMS):
            return None, None
        return (
            ",".join(value for value in scaffold.EXECUNITS if value in formats),
            ",".join(value for value in scaffold.OPERATING_SYSTEMS if value in self.systems),
        )

    @property
    def matrix(self) -> dict[str, set[str]]:
        return scaffold.support_matrix(*self.selection_arguments())

    @property
    def requested_destination(self) -> Path:
        if self.folder:
            return Path(self.folder).expanduser()
        return scaffold.DEFAULT_WORKSPACE_ROOT / f"{self.kind}s" / self.slug

    @property
    def destination(self) -> Path:
        return self.requested_destination.resolve()

    def toggle_system(self, value: str) -> None:
        if value in self.systems:
            if len(self.systems) == 1:
                raise ValueError("Select at least one target platform.")
            self.systems.remove(value)
        else:
            self.systems.add(value)
            if value == "linux":
                self.formats.add("native-lib")

    def toggle_format(self, value: str) -> None:
        if value in self.formats:
            if value == "native-lib" and "linux" in self.systems:
                raise ValueError("Linux requires native-lib. Remove Linux to select only Windows formats.")
            if len(self.formats.intersection(self.available_formats)) == 1:
                raise ValueError("Select at least one execution format.")
            self.formats.remove(value)
        else:
            self.formats.add(value)

    def validate_destination(self) -> None:
        destination = self.destination
        if os.path.lexists(self.requested_destination) or os.path.lexists(destination):
            raise ValueError(f"Destination already exists: {destination}. Choose a new directory.")
        template = (scaffold.REPO_ROOT / "templates" / self.kind).resolve()
        if destination.is_relative_to(template):
            raise ValueError("Choose a destination outside the source template.")

    def create(self) -> tuple[Path, str]:
        if self.kind not in KINDS:
            raise ValueError("Choose a command or listener plugin.")
        self.slug
        self.matrix
        self.validate_destination()
        return scaffold.scaffold(self.kind, self.name, str(self.destination), *self.selection_arguments())


def complete_directory(value: str) -> tuple[str, str]:
    """Complete existing parent directories, preserving literal spaces and '~'."""
    prefix, separator, partial = value.rpartition(os.sep)
    parent = Path(prefix + separator if separator else ".").expanduser()
    matches = sorted(
        child.name for child in parent.iterdir()
        if child.is_dir() and child.name.startswith(partial)
        and (partial.startswith(".") or not child.name.startswith("."))
    )
    if not matches:
        return value, "No matching parent directory. New directories will be created."
    completed = matches[0] + os.sep if len(matches) == 1 else os.path.commonprefix(matches)
    result = prefix + separator + completed
    hint = "Directory completed; add the new plugin folder name."
    if len(matches) > 1:
        hint = "Directories: " + ", ".join(matches[:6]) + (", ..." if len(matches) > 6 else "")
    return result, hint


def display_width(value: str) -> int:
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in ("W", "F") else 1 for char in value)


def clipped(value: str, width: int) -> str:
    result = ""
    for char in value:
        char = char if char.isprintable() else "?"
        if display_width(result + char) > width:
            break
        result += char
    return result


class Wizard:
    def __init__(self, screen) -> None:
        self.screen = screen
        self.plan = PluginPlan()
        self.step = 0
        self.focus = 0
        self.cursor = 0
        self.scroll = 0
        self.message = ""
        self.error = False
        self.accent = self.failure = curses.A_BOLD
        self.screen.keypad(True)
        if hasattr(curses, "set_escdelay"):
            curses.set_escdelay(25)
        if curses.has_colors():
            curses.start_color()
            background = curses.COLOR_BLACK
            try:
                curses.use_default_colors()
                background = -1
            except curses.error:
                pass
            curses.init_pair(1, curses.COLOR_CYAN, background)
            curses.init_pair(2, curses.COLOR_RED, background)
            self.accent = curses.color_pair(1) | curses.A_BOLD
            self.failure = curses.color_pair(2) | curses.A_BOLD

    def put(self, y: int, x: int, value: str, attribute: int = 0, width: Optional[int] = None) -> None:
        rows, columns = self.screen.getmaxyx()
        if not 0 <= y < rows or not 0 <= x < columns - 1:
            return
        value = clipped(value, min(columns - x - 1, width if width is not None else columns))
        try:
            self.screen.addstr(y, x, value, attribute)
        except curses.error:
            # A resize can invalidate coordinates between getmaxyx and addstr.
            pass

    def options(self) -> tuple[str, ...]:
        if self.step == 0:
            return KINDS
        if self.step == 2:
            return scaffold.OPERATING_SYSTEMS
        if self.step == 3:
            return self.plan.available_formats
        return ()

    def body(self, width: int) -> list[tuple[str, int]]:
        lines: list[tuple[str, int]] = []

        def line(value: str = "", style: int = 0) -> None:
            lines.extend((part, style) for part in textwrap.wrap(value, width) or [""])

        if self.step in (0, 2, 3):
            for index, value in enumerate(self.options()):
                if self.step == 0:
                    selected = value == self.plan.kind
                    label = "Command  - run a task and return a result" if value == "command" else \
                            "Listener - receive connections and manage channels"
                    mark = "(*)" if selected else "( )"
                else:
                    selected = value in (self.plan.systems if self.step == 2 else self.plan.formats)
                    label = {"windows": "Windows (x86 and x64)", "linux": "Linux (x64)"}[value] \
                            if self.step == 2 else f"{value}  - {FORMAT_LABELS[value]}"
                    mark = "[x]" if selected else "[ ]"
                line(f"{'>' if index == self.focus else ' '} {mark} {label}",
                     curses.A_REVERSE if index == self.focus else 0)
            line()
            if self.step == 2:
                line("Choose where the plugin will execute. Linux supports native libraries only.")
            elif self.step == 3 and "linux" in self.plan.systems:
                line("native-lib is required for Linux. Windows can also use the other selected formats.")
        elif self.step == 1:
            line()  # Editable field drawn separately.
            line()
            try:
                line(f"Plugin identifier: {self.plan.slug}", self.accent)
                line(f"Suggested folder: {self.plan.destination}")
            except EXPECTED_ERRORS:
                line("Enter a name containing letters or numbers, for example: Daily Check.")
        elif self.step == 4:
            line()
            line()
            line("Resolved destination:")
            try:
                line(str(self.plan.destination), self.accent)
            except EXPECTED_ERRORS as error:
                line(str(error), self.failure)
            line()
            line("Leave blank for the suggested folder. Paths with spaces need no quotes.")
            line("Tab completes parent directories; add a new folder name at the end.")
        else:
            line(f"Type: {self.plan.kind}")
            line(f"Name: {self.plan.name}  ({self.plan.slug})", self.accent)
            line()
            line("Destination:")
            line(str(self.plan.destination), self.accent)
            line()
            for system, formats in self.plan.matrix.items():
                architecture = "x86/x64" if system == "windows" else "x64"
                ordered = ", ".join(value for value in scaffold.EXECUNITS if value in formats)
                line(f"{system.capitalize()} {architecture}: {ordered}")
            line()
            line("Includes Makefile targets: build, install, clean.")
        return lines

    def render(self) -> bool:
        self.screen.erase()
        rows, columns = self.screen.getmaxyx()
        if rows < 22 or columns < 64:
            self.put(0, 0, "Tuoni plugin wizard", self.accent)
            self.put(1, 0, "Resize to at least 64 columns x 22 rows.")
            self.put(3, 0, "Ctrl-C cancels.")
            self.screen.refresh()
            return False
        width = min(92, columns - 6)
        left = (columns - width) // 2
        self.put(1, left, "TUONI  /  New plugin", self.accent)
        self.put(3, left, "  >  ".join(f"[{name}]" if index == self.step else name
                                     for index, name in enumerate(STEPS)), width=width)
        self.put(5, left, f"{self.step + 1} / {len(STEPS)}  {STEPS[self.step]}", self.accent)
        prompts = (
            "Choose the plugin template.", "Give your plugin a descriptive name.",
            "Select the target operating systems.", "Select the execution formats to build.",
            "Choose the exact directory for the new plugin.", "Review your plugin, then press Enter to create it.",
        )
        self.put(6, left, prompts[self.step], width=width)
        try:
            lines = self.body(width)
        except EXPECTED_ERRORS as error:
            lines = [(str(error), self.failure), ("Go back to edit the plugin details.", 0)]
        capacity = rows - 13
        self.scroll = min(self.scroll, max(0, len(lines) - capacity))
        for index, (value, attribute) in enumerate(lines[self.scroll:self.scroll + capacity]):
            self.put(8 + index, left, value, attribute, width)
        if len(lines) > capacity:
            self.put(rows - 5, left, "PgUp/PgDn scroll the details", width=width)
        try:
            curses.curs_set(1 if self.step in (1, 4) else 0)
        except curses.error:
            pass
        cursor_position = None
        if self.step in (1, 4):
            value = self.plan.name if self.step == 1 else self.plan.folder
            visible_start = self.cursor
            while visible_start > 0 and display_width(value[visible_start - 1:self.cursor]) < width - 4:
                visible_start -= 1
            visible = clipped(value[visible_start:], width - 3)
            placeholder = "Plugin name" if self.step == 1 else "Default: workspace folder shown below"
            self.put(8, left, " " * width, curses.A_REVERSE, width)
            self.put(8, left + 1, visible if value else placeholder, curses.A_REVERSE, width - 2)
            cursor_position = (8, left + 1 + display_width(value[visible_start:self.cursor]))
        if self.message:
            for index, part in enumerate(textwrap.wrap(self.message, width)[:2]):
                self.put(rows - 4 + index, left, part, self.failure if self.error else self.accent, width)
        controls = "Enter create  |  Esc/Shift-Tab back  |  Ctrl-C cancel" if self.step == 5 else \
                   "Enter next  |  Esc/Shift-Tab back  |  Ctrl-C cancel"
        self.put(rows - 2, left, controls, width=width)
        extra = "Arrows move  |  Space selects" if self.options() else \
                "Left/Right edit  |  Ctrl-U clear" if self.step == 1 else \
                "Tab complete directory  |  Ctrl-U clear" if self.step == 4 else ""
        self.put(rows - 1, left, extra, width=width)
        if cursor_position is not None:
            self.screen.move(*cursor_position)
        self.screen.refresh()
        return True

    def change_step(self, offset: int) -> None:
        self.step += offset
        self.focus = self.scroll = 0
        if self.step == 0:
            self.focus = KINDS.index(self.plan.kind)
        self.cursor = len(self.plan.name if self.step == 1 else self.plan.folder)
        self.message = ""

    def edit(self, key) -> None:
        value = self.plan.name if self.step == 1 else self.plan.folder
        if key in (curses.KEY_LEFT, "\x02"):
            self.cursor = max(0, self.cursor - 1)
        elif key in (curses.KEY_RIGHT, "\x06"):
            self.cursor = min(len(value), self.cursor + 1)
        elif key in (curses.KEY_HOME, "\x01"):
            self.cursor = 0
        elif key in (curses.KEY_END, "\x05"):
            self.cursor = len(value)
        elif key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            if self.cursor:
                value = value[:self.cursor - 1] + value[self.cursor:]
                self.cursor -= 1
        elif key == curses.KEY_DC:
            value = value[:self.cursor] + value[self.cursor + 1:]
        elif key == "\x15":
            value = ""
            self.cursor = 0
        elif key == "\x0b":
            value = value[:self.cursor]
        elif isinstance(key, str) and key.isprintable():
            value = value[:self.cursor] + key + value[self.cursor:]
            self.cursor += len(key)
        if self.step == 1:
            self.plan.name = value
        else:
            self.plan.folder = value

    def run(self) -> Optional[tuple[Path, str]]:
        while True:
            usable = self.render()
            key = self.screen.get_wch()
            if key == "\x03":
                raise KeyboardInterrupt
            if not usable or key == curses.KEY_RESIZE:
                continue
            self.message = ""
            self.error = False
            try:
                if key in ("\x1b", curses.KEY_BTAB):
                    if self.step == 0:
                        return None
                    self.change_step(-1)
                elif key in ("\n", "\r", curses.KEY_ENTER) or (key == "\t" and self.step != 4):
                    if self.step == 5:
                        if key != "\t":
                            self.message = "Creating plugin..."
                            self.render()
                            return self.plan.create()
                    else:
                        if self.step == 0:
                            self.plan.kind = KINDS[self.focus]
                        elif self.step == 1:
                            self.plan.slug
                        elif self.step == 3:
                            self.plan.matrix
                        elif self.step == 4:
                            self.plan.validate_destination()
                        self.change_step(1)
                elif key == "\t" and self.step == 4:
                    if self.cursor != len(self.plan.folder):
                        self.message = "Move to the end of the path with End or Ctrl-E to complete it."
                    elif not self.plan.folder:
                        self.plan.folder = str(self.plan.destination)
                        self.cursor = len(self.plan.folder)
                    else:
                        self.plan.folder, self.message = complete_directory(self.plan.folder)
                        self.cursor = len(self.plan.folder)
                elif key == curses.KEY_PPAGE:
                    self.scroll = max(0, self.scroll - 5)
                elif key == curses.KEY_NPAGE:
                    self.scroll += 5
                elif self.options():
                    options = self.options()
                    if key in (curses.KEY_UP, curses.KEY_LEFT):
                        self.focus = (self.focus - 1) % len(options)
                    elif key in (curses.KEY_DOWN, curses.KEY_RIGHT):
                        self.focus = (self.focus + 1) % len(options)
                    elif key == " ":
                        value = options[self.focus]
                        if self.step == 0:
                            self.plan.kind = value
                        elif self.step == 2:
                            self.plan.toggle_system(value)
                        else:
                            self.plan.toggle_format(value)
                elif self.step in (1, 4):
                    self.edit(key)
                elif key == curses.KEY_UP:
                    self.scroll = max(0, self.scroll - 1)
                elif key == curses.KEY_DOWN:
                    self.scroll += 1
            except EXPECTED_ERRORS as error:
                self.message = str(error)
                self.error = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactively create a Tuoni command or listener plugin.")
    parser.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("The plugin wizard needs an interactive terminal. Run 'make new' in a terminal.\n"
              "For scripts, use tools/scaffold_plugin.py or make new-command/new-listener.", file=sys.stderr)
        return 1
    if curses is None:
        print("This Python installation has no curses module. Use Python with curses support "
              "on Linux/macOS, or run the wizard in WSL on Windows.", file=sys.stderr)
        return 1
    try:
        # Check terminfo first: some curses implementations exit in initscr on failure.
        curses.setupterm()
        result = curses.wrapper(lambda screen: Wizard(screen).run())
    except KeyboardInterrupt:
        print("Plugin creation cancelled.")
        return 130
    except curses.error as error:
        print(f"Cannot open the terminal UI: {error}. Check TERM and run in a terminal.", file=sys.stderr)
        return 1
    if result is None:
        print("Plugin creation cancelled.")
        return 0
    destination, slug = result
    print(f"Created plugin '{slug}' in {destination}\n\nEdit the generated sources, then:")
    for target in ("build", "install"):
        print("  " + shlex.join(["make", "-C", str(destination), target]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
