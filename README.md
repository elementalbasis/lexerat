# Lexerat

A conlang lexicon parser.



## Installation

Requires Python 3.10 or newer. HTML and LaTeX rendering also require Jinja2.
It is recommended to use XeLaTeX.

```bash
git clone https://github.com/elementalbasis/lexerat.git
cd lexerat
python -m pip install ".[render]"
```

For parsing and JSON output without rendering dependencies, install with
`python -m pip install .` instead. Installation provides both the `lexerat`
Python module and the `lexerat` command. Existing `python lexerat.py`
commands continue to work from the repository.

You can also install the release directly from GitHub:

```bash
python -m pip install "lexerat[render] @ git+https://github.com/elementalbasis/lexerat.git@v0.2.1"
```

Templates and examples are available in the repository and source archive.

### Python usage

```python
from lexerat import parse

entries = parse("@key(viros) @infl(o-stem) @typ(m) @def(man)")
print(entries[0].infl)  # o-stem
```




## Sample usage

```
# For JSON output:
python lexerat.py examples/basic.txt -o dictionary.json

# For HTML output:
python lexerat.py examples/basic.txt --template templates/basic.html.j2 -o dictionary.html

# For LaTeX output:
python lexerat.py examples/basic.txt --template templates/basic.tex.j2 -o dictionary.tex

# To convert LaTeX to PDF:
xelatex dictionary.tex
```



## Macro syntax

Lexerat describes dictionary entries using macros:

```text
@name(argument)
```

Macros apply to the current entry until `@key(...)` or `@expr(...)`
starts a new one. Macro names are case-sensitive.

| Macro | Purpose |
|---|---|
| `@key(lemma, alternatives...)` | Start a dictionary entry |
| `@infl(text)` | Set the current entry's inflection metadata |
| `@ety(text)` | Set the current entry's etymology |
| `@typ(text)` | Set the grammatical type for subsequent definitions |
| `@def(text)` | Add a definition |
| `@expr(text)` | Start an expression entry |
| `@link(lemmas...)` | Associate the current expression with dictionary entries |



### `@key(lemma, alternatives...)`

Start a new dictionary entry. The first argument is its primary lemma;
any remaining arguments are alternative forms.

```text
@key(donom, donosio)
```

Separate forms with commas:

```text
@key(enos, ena, enod)
```

For example, a verb can list its principal parts as follows:

```text
@key(didomi, didymos, dom, dyme, dedoka, dedykme)
```

Each form must be nonempty. Starting a new entry clears the previous
grammatical type.



### `@infl(text)`

Set the current entry's inflection metadata. Its value is plain text:

```text
@key(amo) @infl(1)
@key(viros) @infl(o-stem)
@key(apojekmi) @infl(jekmi)
```

Lexerat assigns no meaning to this value: it can name a class, a model word,
or any convention chosen by the dictionary author. It does not look up
entries, traverse references, or generate inflection tables.

An entry may have only one `@infl` macro. The entire argument is stored as
one string, with surrounding whitespace removed as for other macros. An
empty argument is stored as an empty string. If omitted, the field is `None`
(`null` in JSON).

The value is available as `entry.infl` to Python code and Jinja templates,
and as `"infl"` in JSON output. Like etymology, it belongs to the whole entry
and can also be used in expression entries. Inflectors and other consumers
decide how to interpret it.



### `@ety(text)`

Set the current entry's etymology.

```text
@key(donom) @ety(From PIE *déh₃nom; cf. Latin donum)
```

An entry may have only one `@ety` macro. The entire argument is treated as text.

This macro can also be used in expression entries.



### `@typ(text)`

Set the grammatical type for subsequent definitions in the current entry.

```text
@key(perfect) @typ(adj) @def(without fault or mistake) @def(representing a
completed action; used in grammar, when talking about a tense or verb form)
@typ(v) @def(to make something perfect)
```

The first two definitions have type `adjective`; the third has type `verb`.



### `@def(text)`

Add a definition to the current entry. Repeat the macro to add
additional senses, in order.

```text
@key(viros) @typ(m) @def(man) @def(husband) @def(hero)
```

Each definition keeps the grammatical type that was last specified.
The entire argument is treated as text.

This macro can also be used in expression entries.



### `@expr(text)`

Start a new expression entry.

```text
@expr(when pigs fly) @typ(adverbial phrase) @def(never)
```

The expression must be nonempty. Its entire argument is treated as one
form, including punctuation.

Like `@key`, this macro starts a new current entry and clears the
previous grammatical type. An expression can have its own etymology,
type, and definitions.

Use `@link` to associate it with ordinary dictionary entries.



### `@link(lemmas...)`

Associate the current expression with one or more dictionary entries.

```text
@expr(when pigs fly) @link(when, pig, fly) @def(never)
```

The expression becomes available under both linked entries for templates
to display. For example, under the entry for `pig`, you will be able to see
the expression `when pigs fly`.

- This macro can only be used within an expression entry.
- Targets must be primary lemmas declared with `@key`, not alternative forms.
- Separate targets with commas.
- Targets may be declared before or after the expression.
- Matching is case-sensitive and preserves accents. Canonically
  equivalent Unicode spellings are treated as equal.
- A missing target or multiple entries with the same target lemma
  produces an error.
- Repeated links to the same target are added only once.



## Reverse-indexing

Inside definitions, mark words to include in the reverse dictionary
with `$` or `&`:

```text
@def(a $house or &home)
```

Both markers currently have the same indexing behavior.

Use braces for terms containing spaces or punctuation:

```text
@def(a ${place of residence})
```

Unbraced terms may contain Unicode letters, numbers, combining marks,
underscores, and internal hyphens or apostrophes:

```text
@def(a $mother-in-law)
```

Each marked term points to the entry and the particular definition in
which it appears. Repeated occurrences of the same term within one
definition produce one index match.

The output template controls how markers and index matches are displayed.



## Comments and escaping

A percent sign starts a comment that continues to the end of the line:

```text
% A dictionary entry
@key(donom) % The primary lemma
@def(a $house)
```


Use backslashes for literal syntax characters:

| Input | Literal character |
|---|---|
| `\@` | `@` |
| `\(` | `(` |
| `\)` | `)` |
| `\%` | `%` |
| `\\` | `\` |


Balanced parentheses can appear directly inside arguments:

```text
@def(a house (especially a large one))
```

Macros cannot be nested inside arguments. Use `\@` for a literal `@`.

In definitions, `\$` and `\&` prevent the following text from being
interpreted as a reverse-index term.

Whitespace at the beginning and end of each argument is removed.
Outside macros, only whitespace and comments are allowed.



## Bracketed options

The parser accepts an optional bracketed value immediately after a
macro name:

```text
@name[option](argument)
```

The built-in macro handlers currently do not use this value.



## License

Lexerat is licensed under the [MIT License](LICENSE).



## TO DO

* Make it so that all keywords within the @typ tag are collected, and then the
user can edit a TSV table to set their abbreviations.
* Fix up the basic templates; they should not output `$`.
