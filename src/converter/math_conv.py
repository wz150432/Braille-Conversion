"""LaTeX mathematics → a supported subset of BANA Nemeth Code (2022).

Parse structure before emitting cells. Unsupported/malformed formulas produce
one review marker (⠿) and a warning, rather than an invented transcription.
See docs/math-braille.md for supported notation and clause references.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)
_PLACEHOLDER = '⠿'
_FOLLOWING_PUNCTUATION = frozenset(',.;:!?)]}\'"，。；：、！？）】〉》」』’”')


def needs_space_after_math(text: str, end: int) -> bool:
    """Appendix B: main-text punctuation attaches directly to the terminator."""
    return (end < len(text) and not text[end].isspace() and
            text[end] not in _FOLLOWING_PUNCTUATION)

# BANA Rules 3, 5, 6, 19–21. These are Nemeth cells, not UEB digits.
_LETTERS = dict(zip('abcdefghijklmnopqrstuvwxyz',
                    '⠁⠃⠉⠙⠑⠋⠛⠓⠊⠚⠅⠇⠍⠝⠕⠏⠟⠗⠎⠞⠥⠧⠺⠭⠽⠵'))
_DIGITS = dict(zip('0123456789.', '⠴⠂⠆⠒⠲⠢⠖⠶⠦⠔⠨'))
_OPERATIONS = {
    '+': '⠬', '-': '⠤', '−': '⠤', '±': '⠬⠤', '∓': '⠤⠬',
    '×': '⠈⠡', '÷': '⠨⠌', '*': '⠈⠼', '/': '⠸⠌',
    '⋅': '⠡', '∪': '⠨⠬', '∩': '⠨⠩', '%': '⠈⠴',
    "'": '⠄', '∞': '⠠⠿', '∂': '⠈⠙', '!': '⠯',
}
_RELATIONS = {
    '=': '⠨⠅', '<': '⠐⠅', '>': '⠨⠂', '≤': '⠐⠅⠒',
    '≥': '⠨⠂⠒', '≠': '⠌⠨⠅', '≡': '⠸⠇',
    '∈': '⠈⠑', '⊂': '⠸⠐⠅', '⊃': '⠸⠨⠂',
    '→': '⠫⠕', '←': '⠫⠪⠒⠒',
}
_DELIMITERS = {
    '(': (')', '⠷', '⠾'), '[': (']', '⠈⠷', '⠈⠾'),
    r'\{': (r'\}', '⠨⠷', '⠨⠾'),
    r'\langle': (r'\rangle', '⠨⠨⠷', '⠨⠨⠾'),
    r'\lvert': (r'\rvert', '⠳', '⠳'),
    r'\lVert': (r'\rVert', '⠳⠳', '⠳⠳'),
}
_GREEK = dict(zip(
    ('alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu '
     'nu xi omicron pi rho sigma tau upsilon phi chi psi omega').split(),
    '⠁⠃⠛⠙⠑⠵⠱⠹⠊⠅⠇⠍⠝⠭⠕⠏⠗⠎⠞⠥⠋⠯⠽⠺'))
_GREEK_UNICODE = dict(zip('αβγδεζηθικλμνξοπρστυφχψω', _GREEK))
_ALTERNATE_GREEK = {'vartheta': 'theta', 'varphi': 'phi', 'varsigma': 'sigma'}
_COMMAND_SYMBOLS = {
    'times': '×', 'div': '÷', 'cdot': '⋅', 'pm': '±', 'mp': '∓',
    'le': '≤', 'leq': '≤', 'ge': '≥', 'geq': '≥', 'ne': '≠', 'neq': '≠',
    'equiv': '≡', 'in': '∈', 'subset': '⊂', 'supset': '⊃',
    'to': '→', 'rightarrow': '→', 'leftarrow': '←',
    'cup': '∪', 'cap': '∩', 'infty': '∞', 'partial': '∂', '%': '%',
    'prime': "'",
}
_FUNCTIONS = set(('sin cos tan cot sec csc sinh cosh tanh arcsin arccos arctan '
                  'log ln exp lim max min sup inf').split())
_BIGOPS = {'sum': '⠨⠠⠎', 'prod': '⠨⠠⠏', 'int': '⠮',
           'iint': '⠮⠮', 'iiint': '⠮⠮⠮'}
_TYPEFORMS = {'mathbf': '⠸', 'boldsymbol': '⠸', 'bm': '⠸',
             'mathit': '⠨', 'mathsf': '⠠⠨', 'mathcal': '⠈',
             'mathscr': '⠈', 'mathbb': '⠠⠸', 'mathfrak': 'german'}
_SIZE_COMMANDS = set(('left right big Big bigg Bigg bigl bigr Bigl Bigr '
                      'biggl biggr Biggl Biggr').split())


class Token:
    """A lexical token; argument parsing consumes ONE TeX character if unbraced."""
    __slots__ = ('type', 'value')
    NUMBER = 'NUMBER'
    IDENT = 'IDENT'
    COMMAND = 'COMMAND'
    SYMBOL = 'SYMBOL'
    LBRACE = 'LBRACE'
    RBRACE = 'RBRACE'
    CARET = 'CARET'
    UNDERSCORE = 'UNDERSCORE'
    EOF = 'EOF'

    def __init__(self, type_: str, value: str = ''):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f'Token({self.type}, {self.value!r})'


def tokenize_latex(s: str) -> List[Token]:
    tokens = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '%':
            i = s.find('\n', i)
            if i == -1:
                break
            continue
        if ch == '\\':
            start = i
            i += 1
            if i < len(s) and s[i].isascii() and s[i].isalpha():
                while i < len(s) and s[i].isascii() and s[i].isalpha():
                    i += 1
            elif i < len(s):
                i += 1
            tokens.append(Token(Token.COMMAND, s[start:i]))
            continue
        if ch in '0123456789' or (ch == '.' and i + 1 < len(s)
                                   and s[i + 1] in '0123456789'):
            match = re.match(r'(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)', s[i:])
            value = match.group()
            tokens.append(Token(Token.NUMBER, value))
            i += len(value)
            continue
        kind = {'{': Token.LBRACE, '}': Token.RBRACE,
                '^': Token.CARET, '_': Token.UNDERSCORE}.get(ch, Token.SYMBOL)
        if ch.isascii() and ch.isalpha():
            kind = Token.IDENT
        tokens.append(Token(kind, ch))
        i += 1
    tokens.append(Token(Token.EOF))
    return tokens


@dataclass(frozen=True)
class _Node:
    kind: str
    value: str = ''
    children: tuple = ()


_EMPTY = _Node('sequence')


def _single(node):
    """Unwrap a one-item TeX group without losing actual math delimiters."""
    while node.kind == 'sequence' and len(node.children) == 1:
        node = node.children[0]
    return node


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def take(self):
        token = self.peek()
        if token.type != Token.EOF:
            self.pos += 1
        return token

    def sequence(self, stop=None, *, right_required=False):
        nodes = []
        closed_right = False
        while self.peek().type != Token.EOF:
            if (stop is not None and self.peek().type == Token.COMMAND and
                    self.peek().value[1:] in _SIZE_COMMANDS and
                    self.tokens[self.pos + 1].value == stop):
                command = self.peek().value
                if (command == r'\right') != right_required:
                    raise ValueError('unpaired left/right delimiter')
                closed_right = command == r'\right'
                self.take()
            if self.peek().value == stop:
                if right_required and not closed_right:
                    raise ValueError('left requires matching right')
                break
            base = self.atom()
            if base.kind == 'ignored':
                continue
            primes = 0
            while (base != _Node('operation', "'") and
                   self.peek().value in ("'", r'\prime')):
                self.take()
                primes += 1
            if primes:
                base = _Node('primed', str(primes), (base,))
            mode = 'auto'
            if self.peek().value in (r'\limits', r'\nolimits'):
                if base.kind not in ('bigop', 'function'):
                    raise ValueError('limits requires an operator')
                mode = self.take().value[1:]
            sub = sup = _EMPTY
            while self.peek().type in (Token.CARET, Token.UNDERSCORE):
                kind = self.take().type
                argument = self.argument()
                if not argument.children and argument.kind == 'sequence':
                    raise ValueError('empty script')
                if kind == Token.CARET:
                    if sup != _EMPTY:
                        raise ValueError('duplicate superscript')
                    sup = argument
                else:
                    if sub != _EMPTY:
                        raise ValueError('duplicate subscript')
                    sub = argument
            if sub != _EMPTY or sup != _EMPTY:
                # Primes precede the remaining script (Rule 14.12).
                for script_kind in ('sub', 'sup'):
                    script = sub if script_kind == 'sub' else sup
                    prime_nodes = list(script.children if script.kind == 'sequence' else (script,))
                    primes = 0
                    while prime_nodes and prime_nodes[0] == _Node('operation', "'"):
                        primes += 1
                        prime_nodes.pop(0)
                    if primes:
                        base = _Node('primed', str(primes), (base,))
                        script = _Node('sequence', children=tuple(prime_nodes))
                        if script_kind == 'sub':
                            sub = script
                        else:
                            sup = script
            if sub != _EMPTY or sup != _EMPTY:
                base = _Node('scripts', mode, (base, sub, sup))
            if base.kind == 'sequence':
                nodes.extend(base.children)
            else:
                nodes.append(base)
        if stop is not None:
            if self.peek().value != stop:
                raise ValueError(f'unclosed group: expected {stop}')
            self.take()
        return _Node('sequence', children=tuple(nodes))

    def argument(self):
        return self.atom(single_char=True)

    def atom(self, single_char=False, *, right_required=False):
        tok = self.peek()
        if tok.type == Token.LBRACE:
            self.take()
            return self.sequence('}')
        if tok.value in _DELIMITERS:
            self.take()
            close, left, right = _DELIMITERS[tok.value]
            return _Node('delimited', left + right,
                         (self.sequence(close, right_required=right_required),))
        if tok.type == Token.NUMBER:
            value = tok.value
            if single_char and len(value) > 1:
                # TeX scans a single character, even inside a multi-digit numeral.
                self.tokens[self.pos] = Token(Token.NUMBER, value[1:])
                value = value[0]
            else:
                self.take()
            if value == '.':
                raise ValueError('unbraced decimal argument; use braces')
            return _Node('number', value)
        if tok.type == Token.IDENT:
            self.take()
            return _Node('letter', tok.value)
        if tok.type == Token.COMMAND:
            self.take()
            cmd = tok.value[1:]
            if cmd in ('frac', 'dfrac', 'tfrac'):
                numerator, denominator = self.argument(), self.argument()
                if numerator == _EMPTY or denominator == _EMPTY:
                    raise ValueError('fraction requires numerator and denominator')
                return _Node('fraction', children=(numerator, denominator))
            if cmd == 'sqrt':
                index = _EMPTY
                if self.peek().value == '[':
                    self.take()
                    index = self.sequence(']')
                    if index == _EMPTY:
                        raise ValueError('empty root index')
                radicand = self.argument()
                if radicand == _EMPTY:
                    raise ValueError('radical requires a radicand')
                return _Node('radical', children=(index, radicand))
            if cmd in _SIZE_COMMANDS:
                # A size command must be followed by a recognized delimiter;
                # \left. and \right. need layout/context we do not infer.
                if cmd == 'right':
                    raise ValueError('right without left')
                delimiter = self.take()
                if delimiter.value in ('(', '[', r'\{', r'\langle', r'\lvert', r'\lVert'):
                    self.pos -= 1
                    return self.atom(right_required=cmd == 'left')
                closing = {v[0] for v in _DELIMITERS.values()}
                if delimiter.value in closing:
                    raise ValueError('closing size command should be consumed by group')
                raise ValueError('unsupported sized delimiter')
            if cmd in (',', ';', ':', '!', 'quad', 'qquad', ' '):
                # Visual TeX glue is not semantic Nemeth spacing (Rules 18, 21).
                return _Node('ignored')
            if cmd in ('label', 'tag'):
                if self.peek().type != Token.LBRACE:
                    raise ValueError('metadata requires a group')
                self._skip_metadata()
                return _Node('ignored')
            if cmd in ('nonumber', 'notag'):
                return _Node('ignored')
            if cmd in ('mathrm',):
                arg = self.argument()
                if not all(n.kind == 'letter' for n in self._letters(arg)):
                    raise ValueError('mathrm requires letters')
                return arg
            if cmd in _TYPEFORMS:
                return _Node('typeform', _TYPEFORMS[cmd], (self.argument(),))
            if cmd == 'ell':
                return _Node('typeform', '⠈', (_Node('letter', 'l'),))
            if cmd in _GREEK:
                return _Node('greek', cmd)
            if cmd.lower() in _GREEK and cmd[0].isupper():
                return _Node('greek', cmd)
            if cmd in _ALTERNATE_GREEK:
                return _Node('alternate_greek', _ALTERNATE_GREEK[cmd])
            if cmd in _BIGOPS:
                return _Node('bigop', cmd)
            if cmd in _FUNCTIONS:
                return _Node('function', cmd)
            if cmd in _COMMAND_SYMBOLS:
                return self.symbol(_COMMAND_SYMBOLS[cmd])
            raise ValueError(f'unsupported command: {tok.value}')
        if tok.type == Token.SYMBOL:
            self.take()
            if tok.value in _GREEK_UNICODE:
                return _Node('greek', _GREEK_UNICODE[tok.value])
            if tok.value.lower() in _GREEK_UNICODE and tok.value.isupper():
                name = _GREEK_UNICODE[tok.value.lower()]
                return _Node('greek', name.capitalize())
            return self.symbol(tok.value)
        raise ValueError(f'unexpected token: {tok}')

    @staticmethod
    def symbol(value):
        if value in _OPERATIONS:
            return _Node('operation', value)
        if value in _RELATIONS:
            return _Node('relation', value)
        if value == ',':
            return _Node('comma')
        raise ValueError(f'unsupported symbol: {value}')

    @staticmethod
    def _letters(node):
        return node.children if node.kind == 'sequence' else (node,)

    def _skip_metadata(self):
        depth = 0
        while self.peek().type != Token.EOF:
            tok = self.take()
            depth += (tok.type == Token.LBRACE) - (tok.type == Token.RBRACE)
            if depth == 0:
                return
        raise ValueError('unclosed metadata')


class NemethConverter:
    """Emit supported Nemeth structures with explicit level and numeric state."""
    def __init__(self, tokens: List[Token], *, display=False):
        self.tokens = tokens
        self.display = display
        self.parts = []
        self.level = ()
        self.enclosed_list = False
        self.suppress_number = False

    def emit(self, text):
        self.parts.append(text)

    def move(self, level):
        if self.level != level:
            self.emit(''.join(level) if level else '⠐')
            self.level = level

    def convert(self):
        tree = _Parser(self.tokens).sequence()
        self.render(tree, ())
        return ''.join(self.parts).strip()

    @staticmethod
    def fraction_height(node):
        # Fractions at script level do not change their containing fraction's order.
        if node.kind == 'scripts':
            return NemethConverter.fraction_height(node.children[0])
        child_height = max((NemethConverter.fraction_height(n) for n in node.children), default=0)
        return child_height + (node.kind == 'fraction')

    @staticmethod
    def letter_base(node):
        node = _single(node)
        if node.kind in ('typeform', 'primed'):
            return NemethConverter.letter_base(node.children[0])
        if node.kind in ('letter', 'greek', 'alternate_greek', 'function'):
            return True
        return node.kind == 'bigop' and node.value in ('sum', 'prod')

    @staticmethod
    def implicit_sub(node, level):
        if node.kind != 'scripts' or level:
            return False
        base, sub, _ = node.children
        return NemethConverter.letter_base(base) and _single(sub).kind == 'number'

    @staticmethod
    def ends_letter(node):
        node = _single(node)
        if node.kind == 'sequence' and node.children:
            return NemethConverter.ends_letter(node.children[-1])
        return node.kind in ('letter', 'greek', 'alternate_greek', 'typeform')

    def render(self, node, level, root_depth=0, *, function_space=True, group_contents=False):
        kind = node.kind
        if kind == 'sequence':
            previous = None
            for i, child in enumerate(node.children):
                following = node.children[i + 1] if i + 1 < len(node.children) else None
                before = ''.join(self.parts)
                if (_single(child).kind == 'letter' and
                        not self.enclosed_list and
                        (not before or before.endswith(' ') or
                         (group_contents and i == 0 and following is not None and
                          following.kind == 'comma')) and
                        (following is None or following.kind == 'comma') and
                        (previous is None or previous.kind == 'comma')):
                    self.emit('⠰')  # 6.3.1, with grouping/function/comparison exemptions.
                if (previous is not None and previous.kind == 'operation' and
                        child.kind == 'operation' and
                        previous.value in ('+', '-') and child.value in ('+', '-')):
                    self.move(level)
                    self.emit('⠐')  # 24.1 e: two operations, not a compound ±/∓.
                if _single(child).kind == 'number' and previous is not None:
                    implicit = (self.implicit_sub(previous, level) and
                                previous.children[2] == _EMPTY)
                    if self.level == level and (self.ends_letter(previous) or implicit):
                        self.move(level)
                        self.emit('⠐')  # Rule 24.1 b/c: baseline numeral, not subscript.
                suppressed = self.suppress_number
                at_item_start = previous is None or previous.kind == 'comma'
                if previous == _Node('operation', '-'):
                    at_item_start = i == 1 or node.children[i - 2].kind == 'comma'
                self.suppress_number = self.enclosed_list and at_item_start
                try:
                    self.render(child, level, root_depth)
                finally:
                    self.suppress_number = suppressed
                previous = child
            return
        if kind == 'relation':
            # At baseline the space itself restores baseline (14.8.7).
            # Inside a script, restate that script before the comparison (14.9.5).
            self.emit(' ' + ''.join(level) + _RELATIONS[node.value] + ' ')
            self.level = level
            return
        if kind == 'comma':
            if level:
                self.move(level)
                self.emit('⠻')  # contracted comma, Rule 14.7
            else:
                self.emit('⠠ ')
                self.level = ()
            return
        self.move(level)
        if kind == 'number':
            before = ''.join(self.parts)
            if not self.suppress_number and (not before or before.endswith(' ') or (
                    before.endswith('⠤') and (len(before) == 1 or before[-2] == ' ')) or before.endswith('⠈⠼')):
                self.emit('⠼')
            self.emit(''.join(_DIGITS[ch] for ch in node.value))
        elif kind == 'letter':
            self.emit(('⠠' if node.value.isupper() else '') + _LETTERS[node.value.lower()])
        elif kind in ('greek', 'alternate_greek'):
            self.emit('⠨' + ('⠈' if kind == 'alternate_greek' else '') +
                      ('⠠' if node.value[0].isupper() else '') + _GREEK[node.value.lower()])
        elif kind == 'operation':
            self.emit(_OPERATIONS[node.value])
        elif kind == 'function':
            self.emit(''.join(_LETTERS[c] for c in node.value))
            if function_space:
                self.emit(' ')
        elif kind == 'bigop':
            self.emit(_BIGOPS[node.value])
        elif kind == 'primed':
            self.render(node.children[0], level, root_depth)
            self.move(level)
            self.emit('⠄' * int(node.value))
        elif kind == 'typeform':
            letters = _Parser._letters(node.children[0])
            for letter in letters:
                letter = _single(letter)
                if letter.kind not in ('letter', 'greek', 'alternate_greek'):
                    raise ValueError('typeform supported for individual letters only')
                if node.value == 'german':
                    if letter.kind != 'letter':
                        raise ValueError('German alphabet requires a Latin letter')
                    self.emit('⠸')
                else:
                    self.emit(node.value)
                    if letter.kind == 'letter':
                        self.emit('⠰')
                self.render(letter, level, root_depth)
        elif kind == 'delimited':
            left, right = self._delimiter_cells(node.value)
            self.emit(left)
            previous_list = self.enclosed_list
            self.enclosed_list = self.is_enclosed_list(node.children[0])
            try:
                self.render(node.children[0], level, root_depth, group_contents=True)
            finally:
                self.enclosed_list = previous_list
            self.move(level)
            self.emit(right)
        elif kind == 'fraction':
            num, den = node.children
            # Continued fractions require spatial layout (Rule 13.9).
            if self._continued_fraction(node):
                raise ValueError('continued fraction requires spatial transcription')
            order = '⠠' * (self.fraction_height(node) - 1)
            self.emit(order + '⠹')
            self.render_reduced(num, level, root_depth)
            self.move(level)
            self.emit(order + '⠌')
            self.render_reduced(den, level, root_depth)
            self.move(level)
            self.emit(order + '⠼')
        elif kind == 'radical':
            index, radicand = node.children
            order = '⠨' * root_depth
            if index != _EMPTY:
                self.emit(order + '⠣')
                self.render_reduced(index, level, root_depth + 1)
                self.move(level)
                self.emit('⠜')
            else:
                self.emit(order + '⠜')
            self.render(radicand, level, root_depth + 1)
            self.move(level)
            self.emit(order + '⠻')
        elif kind == 'scripts':
            self._scripts(node, level, root_depth)
        else:
            raise ValueError(f'unsupported structure: {kind}')

    @staticmethod
    def _delimiter_cells(value):
        for _, left, right in _DELIMITERS.values():
            if left + right == value:
                return left, right
        raise ValueError('unknown delimiter pair')

    @staticmethod
    def is_enclosed_list(node):
        def has_relation(n):
            return n.kind == 'relation' or any(has_relation(c) for c in n.children)
        return (node.kind == 'sequence' and any(c.kind == 'comma' for c in node.children)
                and not has_relation(node))

    @staticmethod
    def _continued_fraction(node):
        if node.kind != 'fraction':
            return False
        den = _single(node.children[1])
        if den.kind != 'sequence' or len(den.children) < 2:
            return False
        return (len(den.children) == 3 and
                den.children[0].kind == 'number' and
                den.children[0].value.isdigit() and
                den.children[1] == _Node('operation', '+') and
                den.children[2].kind == 'fraction')

    def _scripts(self, node, level, root_depth):
        base, sub, sup = node.children
        base = _single(base)
        is_function = base.kind == 'function'
        modifiers = node.value == 'limits' or (node.value == 'auto' and self.display and (
            (base.kind == 'bigop' and base.value in ('sum', 'prod')) or
            (is_function and base.value == 'lim')))
        if modifiers:
            if base.kind not in ('bigop', 'function'):
                raise ValueError('unsupported modifier base')
            self.emit('⠐')
            self.render(base, level, root_depth, function_space=False)
            if sub != _EMPTY:
                self.emit('⠩')
                self.render_reduced(sub, level, root_depth)
                self.move(level)
            if sup != _EMPTY:
                self.emit('⠣')
                self.render_reduced(sup, level, root_depth)
                self.move(level)
            self.emit('⠻')
        else:
            self.render(base, level, root_depth, function_space=False)
            if (self.level == level and self.implicit_sub(base, level) and
                    base.children[2] == _EMPTY):
                self.emit('⠐')  # 14-128: grouped, non-simultaneous numeric subscript.
            else:
                self.move(level)  # A grouped base may itself end at another level.
            if sub != _EMPTY:
                if self.implicit_sub(node, level):
                    # Implied numeric subscript has no active level to terminate.
                    self.render_reduced(sub, level, root_depth)
                else:
                    self.move(level + ('⠰',))
                    self.render_reduced(sub, level + ('⠰',), root_depth)
            if sup != _EMPTY:
                self.move(level + ('⠘',))
                self.render_reduced(sup, level + ('⠘',), root_depth)
        if is_function:
            self.emit(' ')
            self.level = level  # Rule 14.8.4 / 18.4: function space restores its level.

    def render_reduced(self, node, level, root_depth):
        """TeX fraction arguments and scripts are below display style."""
        display = self.display
        self.display = False
        try:
            self.render(node, level, root_depth)
        finally:
            self.display = display


# Public API: raw mathematical cells and explicit Nemeth passages.

_MATH_SEGMENT_RE = re.compile(
    r'\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}'
    r'(.*?)\\end\{\1\}'
    r'|\\\[(.+?)\\\]'
    r'|\\\((.+?)\\\)'
    r'|\$\$(.+?)\$\$'
    r'|\$(.+?)\$',
    re.DOTALL,
)


def _math_match_parts(match: re.Match) -> Tuple[str, str]:
    """Return (math kind, expression) for a recognized math segment."""
    if match.group(1) is not None:
        return ('display', match.group(2))
    if match.group(3) is not None:
        return ('display', match.group(3))
    if match.group(4) is not None:
        return ('inline', match.group(4))
    if match.group(5) is not None:
        return ('display', match.group(5))
    return ('inline', match.group(6))


def find_math_segments(text: str) -> List[Tuple[int, int, str, str]]:
    """Find supported math segments with their source positions.

    Returns:
        List[(start, end, kind, expression)].
    """
    segments: List[Tuple[int, int, str, str]] = []
    for match in _MATH_SEGMENT_RE.finditer(text):
        kind, expression = _math_match_parts(match)
        segments.append((match.start(), match.end(), kind, expression))
    return segments


def extract_math_segments(text: str) -> List[Tuple[str, str]]:
    """从文本中提取所有数学片段。

    Args:
        text: 含 LaTeX 数学的原始文本。

    Returns:
        List[(type, expr)]:
          type = 'inline' ($...$) 或 'display' ($$...$$)
          expr = 去掉分隔符后的 LaTeX 表达式
        按在原文中出现顺序返回。
    """
    return [(kind, expression) for _, _, kind, expression in find_math_segments(text)]


def latex_to_nemeth(latex_str: str, *, display: bool = False) -> str:
    """将 LaTeX 数学表达式转换为 Nemeth Code 盲文字符串。

    Args:
        latex_str: LaTeX 数学表达式（不含 $ 分隔符）。
        display: 独立公式的 TeX 样式；影响求和等运算符上下限的位置。

    Returns:
        数学区内部的盲文字符串；不含切换符。不支持或格式错误时返回 ⠿。
    """
    if not latex_str:
        return ''

    try:
        tokens = tokenize_latex(latex_str)
        converter = NemethConverter(tokens, display=display)
        return converter.convert()
    except (ValueError, KeyError, RecursionError) as e:
        logger.warning("数学公式需人工复核（不支持或格式错误）: %s, 输入: %r", e, latex_str)
        return _PLACEHOLDER


def nemeth_passage(expression: str, *, display: bool = False) -> str:
    """Nemeth opening/closing switches with spaces, BANA Rule 4.2 / 4.8.

    This names the imported mathematical code even in Chinese mixed text;
    it does not claim Chinese mathematical Braille compatibility.
    """
    return '⠸⠩ ' + latex_to_nemeth(expression, display=display) + ' ⠸⠱'


def inline_to_nemeth(latex_inline: str) -> str:
    """转换行内数学 $...$ 片段（包含检测 $ 边界）。"""
    return latex_to_nemeth(latex_inline)


def convert_text_with_math(text: str) -> str:
    """将文本中的 $...$ / $$...$$ 数学片段替换为 Nemeth Code。

    Args:
        text: 含 $...$ 数学标记的完整文本。

    Returns:
        数学片段被替换后的文本。
    """
    parts: List[str] = []
    last_end = 0
    for start, end, kind, expression in find_math_segments(text):
        parts.append(text[last_end:start])
        passage = nemeth_passage(expression, display=kind == 'display')
        if parts[-1] and not parts[-1][-1].isspace():
            passage = ' ' + passage
        if needs_space_after_math(text, end):
            passage += ' '
        parts.append(passage)
        last_end = end
    parts.append(text[last_end:])
    return ''.join(parts)
