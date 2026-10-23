# Changelog

## [Unreleased]

- `@ipa(...)` for recording pronounciation.

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
