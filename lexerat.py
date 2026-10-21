"""Lexerat: parse @commands, interpret entries, render with optional Jinja2."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import re
import unicodedata



@dataclass(frozen=True)
class Command:
    name: str
    args: tuple[str, ...]
    option: str | None
    offset: int


class Parser:
    """Balanced delimiters; escaped punctuation; source-positioned diagnostics."""
    def __init__(self, source: str, filename: str = '<string>'):
        self.source = source
        self.filename = filename
        self.i = 0

    def error(self, message, offset=None):
        i = self.i if offset is None else offset
        line = self.source.count('\n', 0, i) + 1
        col = i - self.source.rfind('\n', 0, i)
        return ValueError(f'{self.filename}:{line}:{col}: {message}')

    def parse(self):
        return self.content(False)

    def content(self, argument, split_commas=False):
        nodes, buf, depth = [], [], 0
        def flush():
            if buf:
                nodes.append(''.join(buf))
                buf.clear()
        while self.i < len(self.source):
            char = self.source[self.i]
            if char == '%':
                end = self.source.find('\n', self.i)
                self.i = len(self.source) if end == -1 else end + 1
                continue
            if char == '\\' and self.i + 1 < len(self.source) and self.source[self.i+1] in '@(),\\%':
                buf.append(self.source[self.i+1])
                self.i += 2
                continue
            if argument and depth == 0:
                if char == ')' or (char in ',;' and split_commas):
                    break
            if char == '@':
                if argument:
                    raise self.error(r'commands cannot appear inside arguments; use \@ for literal @')
                flush()
                nodes.append(self.command())
                continue
            if argument:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
            buf.append(char)
            self.i += 1
        flush()
        return tuple(nodes)

    def command(self):
        start = self.i
        self.i += 1
        match = re.match(r'[A-Za-z_][A-Za-z0-9_]*', self.source[self.i:])
        if not match:
            raise self.error('expected command name after @; use \\@ for literal @', start)
        name = match[0]
        self.i += len(name)
        option = None
        if self.i < len(self.source) and self.source[self.i] == '[':
            end = self.source.find(']', self.i + 1)
            if end < 0:
                raise self.error('unclosed command option', start)
            option = self.source[self.i+1:end]
            self.i = end + 1
        if self.i >= len(self.source) or self.source[self.i] != '(':
            raise self.error(f'expected ( after @{name}', start)
        self.i += 1
        args = []
        while True:
            args.append(''.join(
                self.content(True, split_commas=(name in {'key', 'link'}))
                ).strip())
            if self.i >= len(self.source):
                raise self.error(f'unclosed @{name}(...)', start)
            delimiter = self.source[self.i]
            self.i += 1
            if delimiter == ')':
                break
        return Command(name, tuple(args), option, start)



@dataclass
class Definition:
    content: str
    state: dict

    @property
    def typ(self):
        return self.state.get('typ')


@dataclass
class Entry:
    forms: list[str]
    ety: str | None = None
    definitions: list[Definition] = field(default_factory=list)
    kind: str = 'lemma'
    id: str = ''
    links: list[str] = field(default_factory=list)
    expressions: list[Entry] = field(default_factory=list)

    @property
    def lemma(self):
        return self.forms[0]


@dataclass
class Context:
    entries: list[Entry] = field(default_factory=list)
    entry: Entry | None = None
    state: dict = field(default_factory=dict)
    pending_links: list[tuple[Entry, Command]] = field(default_factory=list)

    def require_entry(self):
        if self.entry is None:
            raise ValueError('command must follow @key(...) or @expr(...)')
        return self.entry

    def add_definition(self, content):
        self.require_entry().definitions.append(Definition(content, deepcopy(self.state)))


class Interpreter:
    def __init__(self):
        self.commands = {
                'key': self.key,
                'ety': self.ety,
                'typ': self.typ,
                'def': self.definition,
                'expr': self.expression,
                'link': self.link,
                }

    def command(self, name):
        """Decorator: handler(ctx, command); arguments are plain strings."""
        def register(handler):
            self.commands[name] = handler
            return handler
        return register

    @staticmethod
    def arity(call, count):
        if len(call.args) != count:
            raise ValueError(f'@{call.name} expects {count} argument(s); escape literal commas with \\,')

    def key(self, ctx, call):
        forms = list(call.args)
        if any(not form for form in forms):
            raise ValueError('@key requires nonempty forms')
        ctx.entry = Entry(forms, id=f'entry-{len(ctx.entries) + 1}')
        ctx.entries.append(ctx.entry)
        ctx.state = {}

    def expression(self, ctx, call):
        self.arity(call, 1)
        if not call.args[0]:
            raise ValueError('@expr requires a nonempty expression')
        ctx.entry = Entry(list(call.args), kind='expression',
                          id=f'expr-{len(ctx.entries) + 1}')
        ctx.entries.append(ctx.entry)
        ctx.state = {}

    def link(self, ctx, call):
        entry = ctx.require_entry()
        if entry.kind != 'expression':
            raise ValueError('@link must belong to an @expr entry')
        if any(not target for target in call.args):
            raise ValueError('@link requires nonempty lemma names')
        ctx.pending_links.append((entry, call))

    @staticmethod
    def resolve_links(ctx, parser):
        # Resolve only primary lemmas, after every input has been interpreted.
        # Links store names; parents store references to expressions, so no cycles.
        def normalized(text):
            return unicodedata.normalize('NFC', text.strip())
        by_lemma = {}
        for entry in ctx.entries:
            if entry.kind == 'lemma':
                by_lemma.setdefault(normalized(entry.lemma), []).append(entry)
        for expression, call in ctx.pending_links:
            for name in call.args:
                targets = by_lemma.get(normalized(name), [])
                if not targets:
                    raise parser.error(f'@link target {name!r} has no @key entry', call.offset)
                if len(targets) > 1:
                    raise parser.error(f'@link target {name!r} is ambiguous: multiple @key entries', call.offset)
                target = targets[0]
                if target.lemma not in expression.links:
                    expression.links.append(target.lemma)
                    target.expressions.append(expression)

    def ety(self, ctx, call):
        self.arity(call, 1)
        entry = ctx.require_entry()
        if entry.ety is not None:
            raise ValueError('duplicate @ety in entry')
        entry.ety = call.args[0]

    def typ(self, ctx, call):
        self.arity(call, 1)
        ctx.require_entry()
        ctx.state['typ'] = call.args[0] or None

    def definition(self, ctx, call):
        self.arity(call, 1)
        ctx.add_definition(call.args[0])

    def interpret(self, source, filename='<string>', *, sort=True, sort_key=None):
        parser = Parser(source, filename)
        ctx = Context()
        for node in parser.parse():
            if isinstance(node, str):
                if node.strip():
                    raise ValueError(f'{filename}: text outside a command is not allowed')
                continue
            try:
                if node.name not in self.commands:
                    raise ValueError(f'unknown entry command @{node.name}')
                self.commands[node.name](ctx, node)
            except ValueError as exc:
                raise parser.error(str(exc), node.offset) from exc
        self.resolve_links(ctx, parser)
        if sort:
            key = sort_key or (lambda e: e.lemma.casefold())
            ctx.entries.sort(key=key)
            for entry in ctx.entries:
                entry.expressions.sort(key=key)
        return ctx.entries


def parse(source, filename='<string>', **kwargs):
    return Interpreter().interpret(source, filename, **kwargs)


@dataclass(frozen=True)
class IndexMatch:
    entry: Entry
    definition: Definition
    sense_number: int


def references(text):
    """Yield $word, &word, ${phrase}, and &{phrase} lookup terms.

    Bare terms accept Unicode letters/numbers/marks, underscores, and internal
    hyphens/apostrophes. Use braces for spaces or other punctuation. Backslash
    escapes a following character; an escaped marker is not an index term.
    """
    def word_char(char):
        return char.isalnum() or char == '_' or unicodedata.category(char).startswith('M')

    i = 0
    while i < len(text):
        if text[i] == '\\':
            i += 2
            continue
        if text[i] not in '$&':
            i += 1
            continue
        marker = i
        i += 1
        if i < len(text) and text[i] == '{':
            i += 1
            start, depth = i, 1
            while i < len(text) and depth:
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                if depth:
                    i += 1
            if depth:
                raise ValueError(f'unclosed index reference at character {marker + 1}')
            term = text[start:i]
            i += 1
        else:
            start = i
            while i < len(text):
                if word_char(text[i]):
                    i += 1
                elif (i > start and text[i] in "-'’" and i + 1 < len(text)
                      and word_char(text[i + 1])):
                    i += 1
                else:
                    break
            term = text[start:i]
        term = unicodedata.normalize('NFC', ' '.join(term.split()))
        if term:
            yield term


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
                index.setdefault(term, []).append(match)
    return dict(sorted(index.items(), key=lambda item: (item[0].casefold(), item[0])))


def render(entries, template_path, *, options=None):
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    from markupsafe import escape

    path = Path(template_path)
    env = Environment(
        loader=FileSystemLoader(str(path.resolve().parent)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )

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

    entries = list(entries)
    return env.get_template(path.name).render(
        entries=entries,
        reverse_index=build_reverse_index(entries),
        options=options or {},
    )

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('sources', type=Path, nargs='+')
    cli.add_argument('--template', type=Path)
    cli.add_argument('-o', '--output', type=Path)
    args = cli.parse_args()
    try:
        source = '\n'.join(
                path.read_text(encoding='utf-8') for path in args.sources
                )
        entries = parse(source, '<combined inputs>')
        if args.template:
            result = render(entries, args.template)
        else:
            result = json.dumps([asdict(e) for e in entries], ensure_ascii=False, indent=2)
    except (ValueError, OSError) as exc:
        cli.exit(2, f'{exc}\n')
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result)


if __name__ == '__main__':
    main()

