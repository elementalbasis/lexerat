"""Lexerat: parse @commands, interpret entries, render with optional Jinja2."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import re



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
                if char == ')' or (char == ',' and split_commas):
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
                self.content(True, split_commas=(name == 'key'))
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

    @property
    def lemma(self):
        return self.forms[0]


@dataclass
class Context:
    entries: list[Entry] = field(default_factory=list)
    entry: Entry | None = None
    state: dict = field(default_factory=dict)

    def require_entry(self):
        if self.entry is None:
            raise ValueError('command must follow @key(...)')
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
        ctx.entry = Entry(forms)
        ctx.entries.append(ctx.entry)
        ctx.state = {}

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
                if node.option is not None:
                    raise ValueError(f'@{node.name} does not accept a bracket option')
                self.commands[node.name](ctx, node)
            except ValueError as exc:
                raise parser.error(str(exc), node.offset) from exc
        if sort:
            ctx.entries.sort(key=sort_key or (lambda e: e.lemma.casefold()))
        return ctx.entries


def parse(source, filename='<string>', **kwargs):
    return Interpreter().interpret(source, filename, **kwargs)


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

    return env.get_template(path.name).render(
        entries=entries,
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
