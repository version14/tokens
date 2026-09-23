# Version 14 tokens

The source palette for the Version 14 themes. Tool repositories keep their
native formats and committed generated files; this repository keeps the
semantic colors and the generator that updates those files.

## Generate or verify

Clone the theme repositories next to this repository, then run:

```sh
python3 generate.py --themes-root ../repos --check
python3 generate.py --themes-root ../repos --write
```

`--check` is suitable for CI. It exits non-zero when a committed theme file
does not match the output produced from `tokens.toml`.

The generator deliberately preserves tool-specific structure and pre-blended
UI colors. Those values are represented in the native theme implementations
because they depend on each tool's rendering model; the shared semantic
foreground, background, accent, syntax, and ANSI colors come from this file.

## Theme repository template

The reusable CI workflow is available at
templates/theme-repository/.github/workflows/check-tokens.yml.
It checks out the current token source, runs the generator in verification mode,
and runs on pushes, pull requests, manual dispatches, and weekly.

## Variants

- `dark`: the standard deep-neutral theme
- `black`: pure black editor/terminal surfaces
- `light`: bright neutral surfaces with dark semantic colors

The transparent Helix variant uses the dark semantic palette and only changes
which UI surfaces are painted by Helix.

## Supported repositories

Atuin, gh-dash, Ghostty, Helix, Neovim, Starship, Vim, VS Code, and Zed.

## License

[MIT](./LICENSE) © [Mathieu Souflis](https://mathieusouflis.fr)
