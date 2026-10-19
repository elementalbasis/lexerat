# Lexerat starter

A parser and extensible interpreter for the Lexerat lexicon markup language.

## Commands

* `@key(lemma, ...)`: Starts a new entry. First argument is its sort key; all
other arguments are available for display. Resets entry state.
* `@ety(content)`: Stores the entry's etymology. The template controls its
placement.
* `@typ(value)`: Sets the current type for subsequent definitions. Produces no
output by itself.
* `@def(content)`: Appends a definition, capturing the current type.

## Examples

```
@key(viros) @ety(\pie{wiHrós}; \cf \lat{vir}) @typ(m) @def($man) @def($husband)
@key(mentis) @ety(\pie{méntis}; \cf \lat{mens}, \rus{память}{pámjatʹ}, \eng{mind}) @typ(f) @def($thought)
```
