#!/usr/bin/env python3
"""Generate and verify Version 14 theme files from tokens.toml."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable
import tomllib


ROOT = Path(__file__).resolve().parent
VARIANTS = ("dark", "black", "light")
OVERRIDE_RE = re.compile(
    r'version14-override:\s*([A-Za-z0-9_.-]+)\s*=\s*["\'](#[0-9A-Fa-f]{6,8})["\']'
)


def load_tokens() -> dict[str, dict[str, str]]:
    with (ROOT / "tokens.toml").open("rb") as handle:
        data = tomllib.load(handle)
    if data.get("version") != 1:
        raise ValueError("unsupported tokens.toml version")
    return {variant: data[variant] for variant in VARIANTS}


def color_list(p: dict[str, str], light: bool = False) -> list[str]:
    if light:
        return [p["fg_disabled"], p["red"], p["green"], p["yellow"], p["blue"],
                p["accent_secondary"], p["accent"], p["fg_soft"], p["fg_muted"],
                p["red"], p["green"], p["yellow"], p["blue"],
                p["accent_secondary"], p["accent"], p["fg"]]
    return [p["fg_disabled"], p["red"], p["green"], p["yellow"], p["blue"],
            p["accent_secondary"], p["accent"], p["fg_soft"], p["fg_muted"],
            p["red"], p["green"], p["yellow"], p["blue"],
            p["accent_secondary"], p["accent"], p["fg"]]


def render_atuin(name: str, p: dict[str, str]) -> str:
    return f"""[theme]
name = "{name}"

[colors]
AlertInfo = "{p["blue"]}"
AlertWarn = "{p["yellow"]}"
AlertError = "{p["red"]}"
Annotation = "{p["fg_muted"]}"
Base = "{p["fg"]}"
Guidance = "{p["fg_muted"]}"
Important = "{p["accent"]}"
Title = "{p["accent"]}"
Muted = "{p["fg_muted"]}"
SyntaxCommand = "{p["blue"]}"
SyntaxFlag = "{p["accent_secondary"]}"
SyntaxString = "{p["green"]}"
SyntaxVariable = "{p["accent"]}"
SyntaxOperator = "{p["fg"]}"
SyntaxComment = "{p["fg_muted"]}"
"""


def render_gh_dash(p: dict[str, str]) -> str:
    return f"""theme:
  colors:
    text:
      primary: "{p["fg"]}"
      secondary: "{p["accent"]}"
      inverted: "{p["bg_alt"]}"
      faint: "{p["fg_muted"]}"
      warning: "{p["yellow"]}"
      success: "{p["green"]}"
      actor: "{p["accent"]}"
    background:
      selected: "{p["selected"]}"
    border:
      primary: "{p["accent"]}"
      secondary: "{p["blue"]}"
      faint: "{p["selected"]}"
    icon:
      newcontributor: "{p["accent_secondary"]}"
      contributor: "{p["yellow"]}"
      collaborator: "{p["green"]}"
      member: "{p["blue"]}"
      owner: "{p["accent"]}"
      unknownrole: "{p["fg_muted"]}"
"""


def render_starship(name: str, p: dict[str, str]) -> str:
    return f"""[palettes.{name}]
bg = "{p["bg_alt"]}"
bg_elevated = "{p["bg"]}"
fg = "{p["fg"]}"
fg_muted = "{p["fg_muted"]}"
accent = "{p["accent"]}"
red = "{p["red"]}"
green = "{p["green"]}"
yellow = "{p["yellow"]}"
blue = "{p["blue"]}"
magenta = "{p["accent_secondary"]}"
cyan = "{p["accent"]}"
border = "{p["border"]}"
"""


def render_ghostty(p: dict[str, str], light: bool = False) -> str:
    lines = [f"palette = {i}={color}" for i, color in enumerate(color_list(p, light))]
    lines.extend([
        f"background = {p['bg']}",
        f"foreground = {p['fg']}",
        f"cursor-color = {p['accent']}",
        f"cursor-text = {p['bg']}",
        f"selection-background = {p['selection']}",
        f"selection-foreground = {p['fg']}",
    ])
    return "\n".join(lines) + "\n"


def semantic_replacements(p: dict[str, str]) -> dict[str, str]:
    return {
        "#14171B": p["bg"], "#EBEDEF": p["bg"],
        "#1A1E23": p["bg_alt"], "#0C0D0E": p["bg_alt"],
        "#F4F5F6": p["bg_alt"], "#F2F4F6": p["fg"], "#0D0F11": p["fg"],
        "#6E737A": p["fg_muted"], "#636870": p["fg_muted"],
        "#9CA0A6": p["fg_soft"], "#535960": p["fg_soft"],
        "#4E5660": p["fg_disabled"], "#999FA7": p["fg_disabled"],
        "#B7A2FF": p["accent"], "#5F3BBB": p["accent"],
        "#ED8EF3": p["accent_secondary"], "#8C2293": p["accent_secondary"],
        "#FF5C59": p["red"], "#B91A25": p["red"],
        "#4BDE7F": p["green"], "#166534": p["green"],
        "#FFA85E": p["yellow"], "#8F4400": p["yellow"],
        "#78AFFF": p["blue"], "#0054CB": p["blue"],
    }


def replace_semantic_colors(text: str, variants: Iterable[str], palettes: dict[str, dict[str, str]]) -> str:
    replacements: dict[str, str] = {}
    for variant in variants:
        replacements.update(semantic_replacements(palettes[variant]))
    pattern = re.compile(
        "(" + "|".join(re.escape(value) for value in sorted(replacements, key=len, reverse=True)) + ")"
        r"(?![0-9A-Fa-f])"
    )
    return pattern.sub(lambda match: replacements[match.group(0)], text)


def apply_overrides(generated: str, source: str) -> str:
    """Apply explicit per-file palette overrides declared in source comments."""
    for path, color in OVERRIDE_RE.findall(source):
        key = path.rsplit(".", 1)[-1]
        assignment = re.compile(
            rf'(^\s*{re.escape(key)}\s*=\s*["\'])(#[0-9A-Fa-f]{{6,8}})(["\']\s*(?:#.*)?$)',
            re.MULTILINE,
        )
        generated, count = assignment.subn(rf"\g<1>{color}\g<3>", generated)
        if count == 0:
            raise ValueError(f"override {path} did not match an assignment in the target file")
    return generated


def replace_nvim_palette(text: str, palettes: dict[str, dict[str, str]]) -> str:
    boundaries = [
        ("M.dark = {", "M.black = {", "dark"),
        ("M.black = {", "M.light = {", "black"),
        ("M.light = {", "return M", "light"),
    ]
    for start, end, variant in boundaries:
        before, marker, rest = text.partition(start)
        if not marker:
            continue
        body, end_marker, after = rest.partition(end)
        if not end_marker:
            continue
        text = before + marker + replace_semantic_colors(body, (variant,), palettes) + end_marker + after
    return text


def replace_vim_palette(text: str, palettes: dict[str, dict[str, str]]) -> str:
    blocks = (
        ("if s:style ==# 'dark'\n  let [s:bg_dark", "else\n  let [s:bg_dark"),
        ("if s:style ==# 'dark'\n  let g:terminal_ansi_colors", "else\n  let g:terminal_ansi_colors"),
    )
    for dark_marker, light_marker in blocks:
        start = text.index(dark_marker)
        end = text.index(light_marker, start)
        light_end = text.find("\nendif", end)
        if light_end == -1:
            light_end = len(text)
        dark = text[start:end]
        light = text[end:light_end]
        text = (
            text[:start]
            + replace_semantic_colors(dark, ("dark",), palettes)
            + replace_semantic_colors(light, ("light",), palettes)
            + text[light_end:]
        )
    return text


def replace_zed_theme(text: str, palettes: dict[str, dict[str, str]]) -> str:
    document = json.loads(text)
    for theme in document["themes"]:
        variant = {
            "Version 14 Dark": "dark",
            "Version 14 Black": "black",
            "Version 14 Light": "light",
        }[theme["name"]]

        def visit(value):
            if isinstance(value, dict):
                return {key: visit(item) for key, item in value.items()}
            if isinstance(value, list):
                return [visit(item) for item in value]
            if isinstance(value, str):
                return replace_semantic_colors(value, (variant,), palettes)
            return value

        updated = visit(theme)
        theme.clear()
        theme.update(updated)
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def write_or_check(path: Path, content: str, write: bool, failures: list[str]) -> None:
    if write:
        path.write_text(content)
    elif not path.exists() or path.read_text() != content:
        failures.append(str(path))


def process(themes_root: Path, write: bool) -> list[str]:
    palettes = load_tokens()
    failures: list[str] = []
    outputs: dict[Path, str] = {}

    for variant, name in (("dark", "version14"), ("black", "version14-black"), ("light", "version14-light")):
        if (themes_root / "atuin-theme").exists():
            outputs[themes_root / "atuin-theme" / f"{name}.toml"] = render_atuin(name, palettes[variant])
        if (themes_root / "gh-dash-theme").exists():
            outputs[themes_root / "gh-dash-theme" / f"{name}.yml"] = render_gh_dash(palettes[variant])
        if (themes_root / "starship-theme").exists():
            outputs[themes_root / "starship-theme" / f"{name}.toml"] = render_starship(name, palettes[variant])
        if (themes_root / "ghostty-theme").exists():
            outputs[themes_root / "ghostty-theme" / name] = render_ghostty(palettes[variant], variant == "light")

    helix_files = {
        "version14-dark.toml": ("dark",),
        "version14-black.toml": ("black",),
        "version14-light.toml": ("light",),
        "version14-dark-transparent.toml": ("dark",),
    }
    for filename, variants in helix_files.items():
        source = themes_root / "helix-theme" / filename
        if source.exists():
            source_text = source.read_text()
            outputs[source] = apply_overrides(
                replace_semantic_colors(source_text, variants, palettes),
                source_text,
            )

    nvim = themes_root / "nvim-theme" / "lua/version14/palette.lua"
    if nvim.exists():
        outputs[nvim] = replace_nvim_palette(nvim.read_text(), palettes)
    vim = themes_root / "vim-theme" / "colors/version14.vim"
    if vim.exists():
        outputs[vim] = replace_vim_palette(vim.read_text(), palettes)
    zed = themes_root / "zed-theme" / "themes/version14.json"
    if zed.exists():
        outputs[zed] = replace_zed_theme(zed.read_text(), palettes)

    rich_files = [
        (themes_root / "vscode-theme" / "themes/version14-dark-color-theme.json", ("dark",)),
        (themes_root / "vscode-theme" / "themes/version14-black-color-theme.json", ("black",)),
        (themes_root / "vscode-theme" / "themes/version14-light-color-theme.json", ("light",)),
    ]
    for path, variants in rich_files:
        if path.exists():
            outputs[path] = replace_semantic_colors(path.read_text(), variants, palettes)

    for path, content in outputs.items():
        write_or_check(path, content, write, failures)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--themes-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="verify generated files (the default)")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    failures = process(args.themes_root.resolve(), args.write)
    if failures and not args.write:
        print("Out-of-date generated files:")
        print("\n".join(f"  {path}" for path in failures))
        return 1
    print(f"{'Generated' if args.write else 'Verified'} {len(failures) if args.write else 'supported'} theme files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
