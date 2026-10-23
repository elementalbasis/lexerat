"""Lexerat: parse @macros, interpret entries, render with optional Jinja2."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import re
import unicodedata


# Represents a macro.
@dataclass(frozen=True)
class Macro:
    name: str
    args: tuple[str, ...]
    option: str | None
    offset: int # Position of the @



class Parser:
    """Balanced delimiters; escaped punctuation; source-positioned diagnostics."""
    def __init__(self, source: str, filename: str = '<string>'):
        self.source = source # Entirety of the input text
        self.filename = filename
        self.i = 0 # Position along the input text

    # Give the location of the error.
    def error(self, message, offset=None):
        i = self.i if offset is None else offset
        line = self.source.count('\n', 0, i) + 1
        col = i - self.source.rfind('\n', 0, i)
        return ValueError(f'{self.filename}:{line}:{col}: {message}')

    def parse(self):
        return self.content(False)

    def content(self, is_argument, split_commas=False):
        '''
        Read from the Parser's current position, and collect text and macros.
        Stop at the end of the source. Or if inside an argument, stop at the
        terminating delimiter. Advance self.i as characters are read.

        Args:
            is_argument: Whether it's reading inside a macro argument. Stop
                before a closing parenthesis at depth zero, and reject nested
                macros.
            split_commas: Whether commas and semicolons at depth zero also end
                the argument. Only applies when is_argument is true.

        Returns:
            A tuple of strings and Macro objects. Inside an argument, that tuple
            contains only strings.

        Raises:
            ValueError: if an unescaped @ appears inside an argument, or a macro
                has invalid syntax.

        Advances self.i, leaving any terminating delimiter unconsumed.
        '''

        # Holds the things that are parsed.
        nodes = []

        # This is a temporary list that collects ordinary characters until
        # they're ready to become a single string.
        buf = []

        # Keeps track of how many nested parentheses are currently open inside
        # an argument. Helps us parse something like `@this(with (nesting))`.
        depth = 0

       # Flush buf into nodes
        def flush():
            if buf:
                nodes.append(''.join(buf))
                buf.clear()

        # Parsing loop
        while self.i < len(self.source):
            char = self.source[self.i]

            # Implement LaTeX-style comments
            if char == '%':
                end = self.source.find('\n', self.i)
                self.i = len(self.source) if end == -1 else end + 1
                continue

            # Escape special characters
            #if char == '\\' and self.i + 1 < len(self.source) and self.source[self.i+1] in '@(),\\%':
            nextchar = self.source[self.i+1] if self.i+1<len(self.source) else None
            if char == '\\' and nextchar is not None and nextchar in '@(),\\%':
                buf.append(nextchar)
                self.i += 2
                continue

            # If you reach the end of an argument, break the parsing loop.
            if is_argument and depth == 0:
                if char == ')' or (char in ',;' and split_commas):
                    break

            # Disallow nested macros
            if char == '@':
                if is_argument:
                    raise self.error(r'Nested macros are not allowed. Use \@ for literal @')
                flush()
                nodes.append(self.macro())
                continue

            # Keep track of parenthesis depth
            if is_argument:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1


            buf.append(char)
            self.i += 1

        flush()
        return tuple(nodes)

    # Read one complete macro from the source and return a Macro object
    def macro(self):
        '''
        Read one macro starting at the current `@` character.

        Args:
            None.

        Returns:
            A Macro object containing its name, arguments, optional bracketed
            option, and starting offset in the source.

        Raises:
            ValueError: If the macro name is missing, the option is unclosed,
                the opening parenthesis is missing, the arguments are unclosed,
                or an argument contains an unescaped @.

        Advances self.i past the macro's closing parenthesis.
        '''

        start = self.i # Position of the `@`
        self.i += 1 # First letter of the macro's name

        # Macros can only be constructed from the characters below. If an `@` is
        # not followed by any one of them, this is impermissible.
        match = re.match(r'[A-Za-z_][A-Za-z0-9_]*', self.source[self.i:])
        if not match:
            raise self.error('Expected macro name after @; use \\@ for literal @', start)

        # Fetch the entirety of the macro's name, and jump ahead
        name = match[0]
        self.i += len(name)

        # Parse any options the macro may have, and jump ahead
        option = None
        if self.i < len(self.source) and self.source[self.i] == '[':
            end = self.source.find(']', self.i + 1)
            if end < 0:
                raise self.error('Unclosed macro option', start)
            option = self.source[self.i+1:end]
            self.i = end + 1

        # Scream and yell for incomplete macros
        if self.i >= len(self.source) or self.source[self.i] != '(':
            raise self.error(f'Expected ( after @{name}', start)

        self.i += 1
        args = []
        comma_splitting_macros = ['key', 'link']
        while True:
            # Parse the contents of a macro, and either split them by commas, or
            # leave them as a single string.
            args.append(''.join(
                # Since is_argument=True, content() can only return a tuple of
                # strings, instead of a mixed list of strings and Macro objects.
                self.content(
                    is_argument = True,
                    split_commas=(name in comma_splitting_macros)
                    )
                ).strip())

            # Scream and yell for incomplete macros
            if self.i >= len(self.source):
                raise self.error(f'Unclosed @{name}(...)', start)

            delimiter = self.source[self.i]
            self.i += 1
            if delimiter == ')':
                break

        return Macro(name, tuple(args), option, start)



# Represents a dictionary sense
@dataclass
class Definition:
    content: str

    # Save the settings that are active when @def was called.
    # For example, state = {'typ': 'noun'}
    state: dict

    @property
    def typ(self):
        return self.state.get('typ')



# Represents a full dictionary entry
@dataclass
class Entry:
    # Hold the arguments of the @key macro
    forms: list[str]

    # Hold the etymology
    ety: str | None = None

    # Hold the IPA
    ipa: str | None = None

    # Since Entry is a dataclass, __init__() is defined automatically, so
    # there's some fuckshit that we need to do. We call field() to create a
    # fresh empty list for each entry.
    definitions: list[Definition] = field(default_factory=list)

    # The type of entry. Can be a lemma-type entry or an expression-type entry.
    # Defaults to lemma-type entry.
    kind: str = 'lemma'

    # Hold an id for the entry
    id: str = ''

    # Used for expression-type entries to link to lemmas
    links: list[str] = field(default_factory=list)

    # Used for lemma-type entries to hold the expressions that should be
    # displayed underneath them.
    expressions: list[Entry] = field(default_factory=list)

    @property
    def lemma(self):
        return self.forms[0]



# Holds the parsed data as the macros are processed in order.
@dataclass
class Context:
    # All entries processed thus far
    entries: list[Entry] = field(default_factory=list)

    # The current entry receiving definitions, etymology, etc.
    entry: Entry | None = None

    # Settings currently in effect, such as grammatical type
    state: dict = field(default_factory=dict)

    # Expression links to resolve after all entries have been read
    pending_links: list[tuple[Entry, Macro]] = field(default_factory=list)

    # Ensure that there's a current entry in the context, so that any macros
    # like @def have an entry to attach themselves to
    def require_entry(self):
        if self.entry is None:
            raise ValueError('A macro must follow @key(...) or @expr(...)')
        return self.entry

    def add_definition(self, content):
        self.require_entry().definitions.append(Definition(content, deepcopy(self.state)))



class Interpreter:
    def __init__(self):
        # Dict of handler functions
        self.macros = {
                'key': self.key,
                'ipa': self.ipa,
                'ety': self.ety,
                'typ': self.typ,
                'def': self.definition,
                'expr': self.expression,
                'link': self.link,
                }

    def macro(self, name):
        '''Decorator: handler(ctx, macro); arguments are plain strings.'''
        def register(handler):
            self.macros[name] = handler
            return handler
        return register

    # Handler function for the @key macro
    def key(self, ctx, call):
        # Holds the arguments of the @key macro
        forms = list(call.args)

        # Scream and yell for empty argument
        if any(not form for form in forms):
            raise ValueError('@key requires nonempty forms')

        # Create a new lemma-type entry
        ctx.entry = Entry(forms, id=f'entry-{len(ctx.entries) + 1}')
        ctx.entries.append(ctx.entry)
        ctx.state = {}

    # Handler function for the @expr macro
    def expression(self, ctx, call):
        # Scream and yell for empty argument
        if not call.args[0]:
            raise ValueError('@expr requires a nonempty expression')

        # Create a new expression-type entry
        ctx.entry = Entry(list(call.args), kind='expression',
                          id=f'expr-{len(ctx.entries) + 1}')
        ctx.entries.append(ctx.entry)
        ctx.state = {}

    # Handler function for the @link macro
    def link(self, ctx, call):
        # Scream and yell if there's no current entry in the context
        entry = ctx.require_entry()

        # The @link macro is only valid in an expression-type entry.
        if entry.kind != 'expression':
            raise ValueError('@link must belong to an @expr entry')

        # Ensure that @link contains actual lemmas, and not just empty args.
        if any(not target for target in call.args):
            raise ValueError('@link requires nonempty lemma names')

        ctx.pending_links.append((entry, call))

    # Connect expressions to the dictionary entries named in their @link macros.
    @staticmethod
    def resolve_links(ctx, parser):
        # Normalize things like accented characters into a single consistent
        # format.
        def normalized(text):
            return unicodedata.normalize('NFC', text.strip())

        # Create a dict that takes lemmas to their corresponding entries. Allows
        # for the possibility that multiple entries may exist for the same
        # lemma.
        by_lemma = {}
        for entry in ctx.entries:
            # We only care about lemma-type entries; we want to ignore
            # expression-type entries.
            if entry.kind == 'lemma':
                #by_lemma.setdefault(normalized(entry.lemma), []).append(entry)
                name = normalized(entry.lemma)
                if name not in by_lemma:
                    by_lemma[name] = []
                by_lemma[name].append(entry)

        # Connect pending expression-type entries to their corresponding lemmas.
        for expression, call in ctx.pending_links:
            for name in call.args:
                targets = by_lemma.get(normalized(name), [])

                # Scream and yell if there either more than one target or no
                # targets.
                if not targets:
                    msg = f'@link target {name!r} has no @key entry'
                    raise parser.error(msg, call.offset)
                if len(targets) > 1:
                    msg = f'@link target {name!r} is ambiguous: multiple @key entries'
                    raise parser.error(msg, call.offset)

                # Make the mutual connection
                target = targets[0]
                if target.lemma not in expression.links:
                    expression.links.append(target.lemma)
                    target.expressions.append(expression)

    # Handler function for the @ety macro
    def ety(self, ctx, call):
        entry = ctx.require_entry()
        if entry.ety is not None:
            raise ValueError('Duplicate @ety in entry')
        entry.ety = call.args[0]

    # Handler function for the @ipa macro
    def ipa(self, ctx, call):
        entry = ctx.require_entry()
        if entry.ipa is not None:
            raise ValueError('Duplicate @ipa in entry')
        entry.ipa = call.args[0]

    # Handler function for the @typ macro. This macro sets the grammatical type
    # that should be assumed for any subsequent @def macros.
    def typ(self, ctx, call):
        ctx.require_entry()
        ctx.state['typ'] = call.args[0] or None

    # Handler function for the @def macro.
    def definition(self, ctx, call):
        ctx.add_definition(call.args[0])

    # Take the source text, process all its macros, and return a completed
    # dictionary.
    def interpret(self, source, filename='<string>', *, sort=True, sort_key=None):
        parser = Parser(source, filename)
        ctx = Context()

        # First pass, read all the macros
        for node in parser.parse():
            # Disallow orphan strings that do not belong to any macro.
            if isinstance(node, str):
                if node.strip():
                    raise ValueError(f'{filename}: text outside a macro is not allowed')
                continue

            try:
                # Scream and yell if you see an unknown macro
                if node.name not in self.macros:
                    raise ValueError(f'unknown entry macro @{node.name}')

                # Call the current macro's handler function
                self.macros[node.name](ctx, node)
            except ValueError as exc:
                raise parser.error(str(exc), node.offset) from exc

        # After the first pass, resolve any links that were produced by the
        # @expr macros.
        self.resolve_links(ctx, parser)

        if sort:
            # Do not count leading hyphens towards sorting, nor capital letters
            key = sort_key or (lambda e: e.lemma.lstrip('-').casefold())

            ctx.entries.sort(key=key)
            for entry in ctx.entries:
                entry.expressions.sort(key=key)

        return ctx.entries



def parse(source, filename='<string>', **kwargs):
    return Interpreter().interpret(source, filename, **kwargs)



# Represents a result in the reverse dictionary
@dataclass(frozen=True)
class IndexMatch:
    entry: Entry
    definition: Definition
    sense_number: int



# Find the words marked for inclusion in the reverse dictionary.
def references(text):
    '''
    Yield $word, &word, ${phrase}, and &{phrase} lookup terms.

    Bare terms accept Unicode letters/numbers/marks, underscores, and internal
    hyphens/apostrophes. Use braces for spaces or other punctuation. Backslash
    escapes a following character; an escaped marker is not an index term.
    '''

    # Check whether a character is allowed as part of a bare reverse dictionary
    # reference, like $house
    def is_word_char(char):
        return (
                # Allow alphanumeric
                char.isalnum()

                # Allow underscores
                or char == '_'

                # Allow unicode marks such as combining accents
                or unicodedata.category(char).startswith('M')
                )

    i = 0
    while i < len(text):
        # Allow character escaping
        if text[i] == '\\':
            i += 2
            continue

        # References are defined by the special characters $ and &
        if text[i] not in '$&':
            i += 1
            continue

        # Start of the reference, either a $ or &
        marker = i
        i += 1

        # Allow for multi-word references using curly braces
        if i < len(text) and text[i] == '{':
            i += 1
            start = i
            depth = 1

            # Parse the inside of the curly braces
            while i < len(text) and depth:
                # Allow character escaping
                if text[i] == '\\':
                    i += 2
                    continue

                # Handle nested curly braces
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1

                # Advance only if we're still inside curly braces
                if depth:
                    i += 1

            # Scream and yell for unclosed curly braces
            if depth:
                raise ValueError(f'unclosed index reference at character {marker + 1}')

            term = text[start:i]
            i += 1
        # Parse non-curly-brace references
        else:
            start = i
            while i < len(text):
                if is_word_char(text[i]):
                    i += 1

                # Allow hyphens or apostrophes inside a word, provided that:
                # (1) we've already read part of the word, (2) the character is a
                # hyphen, straight apostrophe, or curly apostrophe, and (3) the
                # next character can belong to the word.
                # Thus, $mother-in-law and $don't are valid, but $house- is not.
                #
                # NOTE: I think this is overkill. The most I'd concede are
                # hyphens. But apostrophes too? That's just too much.
                elif (i > start and text[i] in "-'’" and i + 1 < len(text)
                      and is_word_char(text[i + 1])):
                    i += 1
                else:
                    break
            term = text[start:i]

        # Normalize things like accented characters into a single consistent
        # format.
        term = unicodedata.normalize('NFC', ' '.join(term.split()))
        if term:
            yield term



# Build a reverse index. Useful for making a two-way dictionary
def build_reverse_index(entries):
    """Group marked terms by original entry/definition, including expressions.

    Only independent entries are visited: linked display copies in
    entry.expressions must not be traversed a second time.
    """
    index = {}
    seen_entries = set()
    for entry in entries:
        if id(entry) in seen_entries:
            continue
        seen_entries.add(id(entry))
        for number, definition in enumerate(entry.definitions, 1):
            try:
                terms = dict.fromkeys(references(definition.content))
            except ValueError as exc:
                raise ValueError(f'{entry.lemma!r}, definition {number}: {exc}') from exc
            match = IndexMatch(entry, definition, number)
            for term in terms:
                if term not in index:
                    index[term] = []
                index[term].append(match)
    return dict(sorted(
        index.items(),
        key=lambda item: (
            # When sorting, ignore leading hyphens or capital letters
            item[0].lstrip('-').casefold(),
            item[0]
            ),
        ))



# Render with Jinja
def render(entries, template_path, *, options=None):
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    from markupsafe import escape

    # Load the Jinja environment
    path = Path(template_path)
    env = Environment(
        loader=FileSystemLoader(str(path.resolve().parent)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )

    # Handle characters that need to be escaped in either HTML or LaTeX. For
    # example, "house & home" needs to be "house &amp; home" in HTML, while
    # something like "50%" needs to be "50\%" in LaTeX.
    latex_chars = {
        '\\': r'\textbackslash{}',
        '{': r'\{', '}': r'\}',
        '$': r'\$', '&': r'\&',
        '#': r'\#', '%': r'\%',
        '_': r'\_', '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }
    env.filters['html_escape'] = lambda text: escape(
        '' if text is None else str(text)
    )
    env.filters['latex_escape'] = lambda text: ''.join(
        latex_chars.get(c, c)
        for c in ('' if text is None else str(text))
    )

    # Render the result using a given template
    entries = list(entries)
    return env.get_template(path.name).render(
        entries=entries,
        reverse_index=build_reverse_index(entries),
        options=options or {},
    )



def main():
    # Handle the CLI arguments
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('sources', type=Path, nargs='+')
    cli.add_argument('--template', type=Path)
    cli.add_argument('-o', '--output', type=Path)
    args = cli.parse_args()

    try:
        # Read the sources
        source = '\n'.join(
                path.read_text(encoding='utf-8') for path in args.sources
                )

        # Gather the entries
        entries = parse(source, '<combined inputs>')

        # Render
        if args.template:
            result = render(entries, args.template)
        else:
            result = json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=2)
    except (ValueError, OSError) as exc:
        cli.exit(2, f'{exc}\n')

    # Output to file or print
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result)


if __name__ == '__main__':
    main()

