# This Python file uses the following encoding: utf-8
"""Shared utilities for parsing OAS translation sources.

The Chinese translation source of truth is:

    OASX-master/lib/config/translation/i18n_cn.dart

This module parses that file (and the constant definitions in
i18n_content.dart) so that other dev_tools scripts can generate the
runtime JSON/XML files and validate that every config key has a
translation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class I18nEntry:
    """A single key/value entry together with its origin map."""

    key: str
    value: str
    map_name: str


class DartStringParser:
    """Extract a Dart string literal starting at the current position."""

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def skip_irrelevant(self) -> None:
        """Skip whitespace and commas."""
        while self.pos < self.length and self.text[self.pos] in " \t\n\r,":
            self.pos += 1

    def _peek(self, n: int = 1) -> str:
        return self.text[self.pos : self.pos + n]

    def _unescape(self, s: str) -> str:
        """Undo a small subset of Dart string escapes used in this project."""

        def repl(match: re.Match) -> str:
            char = match.group(1)
            return {
                "n": "\n",
                "t": "\t",
                "r": "\r",
                "'": "'",
                '"': '"',
                "\\": "\\",
                "$": "$",
            }.get(char, match.group(0))

        return re.sub(r"\\(.)", repl, s)

    def parse_string_literal(self) -> str:
        """Parse a normal/raw, single/triple quoted Dart string."""
        raw = False
        if self._peek().lower() == "r" and self._peek(2)[1] in "'\"":
            raw = True
            self.pos += 1

        quote = self.text[self.pos]
        if quote not in "'\"":
            raise ValueError(f"Expected string literal at position {self.pos}")

        triple = self.text[self.pos : self.pos + 3] == quote * 3
        if triple:
            end_quote = quote * 3
            self.pos += 3
            end = self.text.find(end_quote, self.pos)
            if end == -1:
                raise ValueError("Unterminated triple-quoted string")
            value = self.text[self.pos : end]
            self.pos = end + 3
            return value if raw else self._unescape(value)

        self.pos += 1
        start = self.pos
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch == "\\" and not raw:
                self.pos += 2
                continue
            if ch == quote:
                value = self.text[start : self.pos]
                self.pos += 1
                return value if raw else self._unescape(value)
            self.pos += 1
        raise ValueError("Unterminated string literal")

    def parse_identifier_key(self, constants: Dict[str, str]) -> str:
        """Parse `I18n.foo` and resolve it to the constant string value."""
        if not self.text.startswith("I18n.", self.pos):
            raise ValueError(f"Expected I18n.* at position {self.pos}")
        self.pos += 5
        start = self.pos
        while (
            self.pos < self.length
            and (self.text[self.pos].isalnum() or self.text[self.pos] == "_")
        ):
            self.pos += 1
        name = self.text[start : self.pos]
        if name not in constants:
            raise ValueError(f"Undefined I18n constant: {name}")
        return constants[name]

    def parse_map_entries(
        self, constants: Dict[str, str]
    ) -> List[Tuple[str, str]]:
        """Parse all key:value pairs until the end of the map body."""
        entries: List[Tuple[str, str]] = []
        while True:
            self.skip_irrelevant()
            if self.pos >= self.length or self.text[self.pos] == "}":
                break

            if self.text.startswith("I18n.", self.pos):
                key = self.parse_identifier_key(constants)
            else:
                key = self.parse_string_literal()

            self.skip_irrelevant()
            if self._peek() != ":":
                raise ValueError(f"Expected ':' after key at position {self.pos}")
            self.pos += 1

            self.skip_irrelevant()
            value = self.parse_string_literal()
            entries.append((key, value))
        return entries


def parse_i18n_content_constants(file_path: Path) -> Dict[str, str]:
    """Parse `static const String name = 'value';` entries."""
    text = file_path.read_text(encoding="utf-8")
    constants: Dict[str, str] = {}
    # Values may be split across lines (e.g. detailed_submission_history).
    pattern = re.compile(
        r"static const String (\w+)\s*=\s*(['\"])(.*?)\2;", re.DOTALL
    )
    for name, _quote, value in pattern.findall(text):
        constants[name] = value
    return constants


def strip_dart_line_comments(text: str) -> str:
    """Remove `//` comments; safe because current translation values do not
    contain `//`."""
    return re.sub(r"//.*$", "", text, flags=re.MULTILINE)


def parse_i18n_cn(
    file_path: Path, constants: Dict[str, str]
) -> Tuple[Dict[str, str], List[I18nEntry], List[str]]:
    """Parse all `_cn_*` maps in `i18n_cn.dart`.

    Returns:
        merged: key -> value dictionary preserving first-appearance order.
        entries: every entry with origin map name (for collision detection).
        warnings: human-readable collision/duplicate messages.
    """
    text = file_path.read_text(encoding="utf-8")

    merged: Dict[str, str] = {}
    entries: List[I18nEntry] = []
    warnings: List[str] = []

    map_pattern = re.compile(
        r"final Map<String, String> (_cn_\w+) = \{(.*?)\};", re.DOTALL
    )

    for match in map_pattern.finditer(text):
        map_name = match.group(1)
        body = strip_dart_line_comments(match.group(2))

        parser = DartStringParser(body)
        try:
            pairs = parser.parse_map_entries(constants)
        except ValueError as exc:
            raise ValueError(f"Failed to parse map {map_name}: {exc}") from exc

        for key, value in pairs:
            entries.append(I18nEntry(key=key, value=value, map_name=map_name))
            if key in merged:
                if merged[key] != value:
                    warnings.append(
                        f"Collision: key '{key}' overwritten in {map_name} "
                        f"(previous: {merged[key]!r}, new: {value!r})"
                    )
                else:
                    warnings.append(
                        f"Duplicate: key '{key}' redefined with same value in {map_name}"
                    )
            merged[key] = value

    return merged, entries, warnings
