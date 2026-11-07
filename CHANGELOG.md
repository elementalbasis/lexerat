# Changelog

## [Unreleased]



## [0.2.1] - 2026-11-06

### Added

- Python packaging metadata for installation with pip and import as `lexerat`.
- Installed `lexerat` command, alongside the existing script interface.
- Optional `render` dependency group for Jinja2.
- Installation and Python API examples in the README.
- Templates, examples, tests, and changelog in the source distribution.



## [0.2.0] - 2026-11-06

- Added `@ipa(...)` for recording pronunciation.
- Semicolons no longer allowed as field separators; only commas.
- Added `@infl(...)` for recording inflection metadata.

### Known limitations

- There can currently only be a single `@ipa` tag per entry.
- The `@ipa` tag does not throw an error if empty.



## [0.1.0] - 2026-10-22

First public release.

### Added

- Macro-based lexicon format: `@key`, `@ety`, `@typ`, `@def`,
  `@expr`, and `@link`.
- Alternative forms, multiple definitions, and grammatical types.
- Expression links to dictionary entries.
- Reverse indexing using `$` and `&` markers.
- JSON output and HTML/LaTeX rendering through Jinja2 templates.
- Basic HTML and LaTeX templates.
- Spanish–English example dictionary.
- Macro syntax and usage documentation.

### Known limitations

- Basic templates display reverse-index markers literally and do not
  display the reverse dictionary.
- Bracketed macro options are parsed but unused by built-in handlers.
- The input format and Python API may change before version 1.0.0.
