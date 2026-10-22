# Lexerat

A conlang lexicon parser.


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

Separate forms with commas or semicolons:

```text
@key(enos; ena; enod)
```

And mix them if it suits your purposes:

```text
@key(didomi, didymos; dom, dyme; dedoka, dedykme)
```

Each form must be nonempty. Starting a new entry clears the previous
grammatical type.



### `@ety(text)`

Set the current entry's etymology.

```text
@key(donom) @ety(From PIE *déh₃nom; cf. Latin donum)
```

An entry may have only one `@ety` macro. Commas and semicolons are
treated as ordinary text.

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
Commas and semicolons are treated as ordinary text.

This macro can also be used in expression entries.



### `@expr(text)`

Start a new expression entry.

```text
@expr(when pigs fly) @typ(adverbial phrase) @def(never)
```

The expression must be nonempty. Its entire argument is treated as one
form, including any commas or semicolons.

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
- Separate targets with commas or semicolons.
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






## TO DO

* Make it so that all keywords within the @typ tag are collected, and then the
user can edit a TSV table to set their abbreviations.
