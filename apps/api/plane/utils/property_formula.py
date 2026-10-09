# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import ast
import datetime
import math
import operator as op
import re
import typing as t

type JsonValue = t.Union[None, bool, int, float, str, t.List[JsonValue], t.Dict[str, JsonValue]]
FormulaValue: t.TypeAlias = t.Union[None, bool, int, float, str, datetime.date]
FormulaNumber: t.TypeAlias = t.Union[int, float]
type FormulaNode = t.Union[
    t.Tuple[t.Literal["value"], t.Union[str, int, float, bool]],
    t.Tuple[t.Literal["reference"], str],
    t.Tuple[t.Literal["unary"], str, FormulaNode],
    t.Tuple[t.Literal["binary"], str, FormulaNode, FormulaNode],
    t.Tuple[t.Literal["function"], str, t.List[FormulaNode]],
]


class FormulaError(ValueError):
    pass


def normalize_formula_reference_name(value: str) -> str:
    return re.sub(r"[\s_]+", "_", value.strip().lower())


class Formula:
    def __init__(self, expression: str) -> None:
        self.tokens: t.List[str] = []
        self.references: t.Set[str] = set()
        self.position: int = 0
        offset: int = 0
        match: t.Optional[t.Match[str]]
        TOKEN_PATTERN: t.Pattern[str] = re.compile(
            r'\s*(?:(\{\{[^{}]+\}\})|(\d+(?:\.\d*)?|\.\d+)|("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')|([A-Za-z_][A-Za-z_0-9]*)|(!=|<=|>=|[+*/&=<>(),-]))'
        )
        while offset < len(expression.rstrip()):
            match = TOKEN_PATTERN.match(expression, offset)
            if not match:
                raise FormulaError(f"Invalid expression at character {offset + 1}.")
            self.tokens.append(next(value for value in match.groups() if value is not None))
            offset = match.end()
        self.tree: FormulaNode = self.parse(0)
        if self.position != len(self.tokens):
            raise FormulaError("Unexpected expression token.")

    def take_next_token(self) -> str:
        if self.position == len(self.tokens):
            raise FormulaError("Expression ended unexpectedly.")
        token: str = self.tokens[self.position]
        self.position += 1
        return token

    def parse(self, precedence: int) -> FormulaNode:
        token: str = self.take_next_token()
        node: FormulaNode
        name: str
        FUNCTION_ARGUMENT_LIMITS: t.Dict[str, t.Tuple[int, int]] = {
            "IF": (3, 3),
            "ROUND": (1, 2),
            "ABS": (1, 1),
            "UPPER": (1, 1),
            "LOWER": (1, 1),
            "LEN": (1, 1),
            "CONCAT": (1, 32),
            "TODAY": (0, 0),
            "NOW": (0, 0),
        }
        if token in ("+", "-"):
            node = ("unary", token, self.parse(5))
        elif token == "(":
            node = self.parse(0)
            if self.take_next_token() != ")":
                raise FormulaError("Missing closing parenthesis.")
        elif token.startswith("{{"):
            name = normalize_formula_reference_name(token[2:-2])
            self.references.add(name)
            node = ("reference", name)
        elif token[0] in ('"', "'"):
            value: str
            error: SyntaxError
            try:
                value = ast.literal_eval(token)
            except SyntaxError as error:
                raise FormulaError(f"Invalid string literal: {error.msg}.") from error
            node = ("value", value)
        elif token[0].isdigit() or token[0] == ".":
            node = ("value", int(token) if token.isdigit() else float(token))
        elif token.upper() in ("TRUE", "FALSE"):
            node = ("value", token.upper() == "TRUE")
        elif token.upper() in FUNCTION_ARGUMENT_LIMITS:
            name = token.upper()
            arguments: t.List[FormulaNode] = []
            if self.take_next_token() != "(":
                raise FormulaError("Functions require parentheses.")
            if self.position < len(self.tokens) and self.tokens[self.position] != ")":
                while True:
                    arguments.append(self.parse(0))
                    if self.position == len(self.tokens) or self.tokens[self.position] != ",":
                        break
                    self.take_next_token()
            if self.take_next_token() != ")":
                raise FormulaError("Missing closing function parenthesis.")
            minimum: int
            maximum: int
            minimum, maximum = FUNCTION_ARGUMENT_LIMITS[name]
            if not minimum <= len(arguments) <= maximum:
                raise FormulaError(f"{name} takes {minimum} to {maximum} arguments.")
            node = ("function", name, arguments)
        else:
            raise FormulaError(f"Unknown function or token: {token}.")
        PRECEDENCE: t.Dict[str, int] = {
            "=": 1,
            "!=": 1,
            "<": 1,
            "<=": 1,
            ">": 1,
            ">=": 1,
            "&": 2,
            "+": 3,
            "-": 3,
            "*": 4,
            "/": 4,
        }
        while self.position < len(self.tokens):
            operator: str = self.tokens[self.position]
            strength: int = PRECEDENCE.get(operator, -1)
            if strength < precedence:
                break
            self.take_next_token()
            node = ("binary", operator, node, self.parse(strength + 1))
        return node

    def evaluate(self, values: t.Mapping[str, FormulaValue], now: t.Optional[datetime.datetime] = None) -> JsonValue:
        now = now or datetime.datetime.now(datetime.timezone.utc)

        def validate_number(value: FormulaValue) -> FormulaNumber:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise FormulaError("Expected a finite number.")
            return value

        def evaluate_node(node: FormulaNode) -> FormulaValue:
            if node[0] == "value":
                return node[1]
            if node[0] == "reference":
                if node[1] not in values:
                    raise FormulaError(f"Unknown property: {node[1]}.")
                return values[node[1]]
            if node[0] == "unary":
                value: FormulaValue = evaluate_node(node[2])
                return None if value is None else validate_number(value) * (-1 if node[1] == "-" else 1)
            if node[0] == "binary":
                operator: str = node[1]
                left: FormulaValue = evaluate_node(node[2])
                right: FormulaValue = evaluate_node(node[3])
                if left is None or right is None:
                    return None
                if operator == "&":
                    return str(left) + str(right)
                # NOW() is a datetime, TODAY() and date properties are dates: Python neither
                # compares nor subtracts the two, so the date becomes its midnight.
                if (
                    isinstance(left, datetime.date)
                    and isinstance(right, datetime.date)
                    and type(left) is not type(right)
                ):
                    midnight: datetime.time = datetime.time(tzinfo=now.tzinfo)
                    left = left if isinstance(left, datetime.datetime) else datetime.datetime.combine(left, midnight)
                    right = (
                        right if isinstance(right, datetime.datetime) else datetime.datetime.combine(right, midnight)
                    )
                COMPARISONS: t.Dict[str, t.Callable[[t.Any, t.Any], bool]] = {
                    "=": op.eq,
                    "!=": op.ne,
                    "<": op.lt,
                    "<=": op.le,
                    ">": op.gt,
                    ">=": op.ge,
                }
                if operator in COMPARISONS:
                    return COMPARISONS[operator](left, right)
                if isinstance(left, datetime.date):
                    if operator == "-" and isinstance(right, datetime.date):
                        return (left - right).days
                    if operator in ("+", "-"):
                        right = validate_number(right)
                        if right == int(right):
                            return left + datetime.timedelta(days=right * (1 if operator == "+" else -1))
                    raise FormulaError("Dates support subtraction or whole-day offsets.")
                left, right = validate_number(left), validate_number(right)
                if operator == "/" and right == 0:
                    raise FormulaError("Division by zero.")
                ARITHMETIC: t.Dict[str, t.Callable[[FormulaNumber, FormulaNumber], FormulaNumber]] = {
                    "+": op.add,
                    "-": op.sub,
                    "*": op.mul,
                    "/": op.truediv,
                }
                return ARITHMETIC[operator](left, right)
            name: str = node[1]
            arguments: t.List[FormulaNode] = node[2]
            if name == "IF":
                condition: FormulaValue = evaluate_node(arguments[0])
                return None if condition is None else evaluate_node(arguments[1] if condition else arguments[2])
            if name in ("TODAY", "NOW"):
                return now.date() if name == "TODAY" else now
            evaluated: t.List[FormulaValue] = [evaluate_node(argument) for argument in arguments]
            if any(value is None for value in evaluated):
                return None
            if name == "ROUND":
                digits: FormulaNumber = validate_number(evaluated[1]) if len(evaluated) == 2 else 0
                if digits != int(digits):
                    raise FormulaError("ROUND precision must be a whole number.")
                return round(validate_number(evaluated[0]), int(digits))
            if name == "ABS":
                return abs(validate_number(evaluated[0]))
            if name == "CONCAT":
                return "".join(str(value) for value in evaluated)
            if not isinstance(evaluated[0], str):
                raise FormulaError(f"{name} requires text.")
            if name == "UPPER":
                return evaluated[0].upper()
            if name == "LOWER":
                return evaluated[0].lower()
            return len(evaluated[0])

        error: t.Union[TypeError, ValueError, OverflowError]
        try:
            result: FormulaValue = evaluate_node(self.tree)
            if isinstance(result, (int, float)) and not isinstance(result, bool):
                validate_number(result)
            return result.isoformat() if isinstance(result, datetime.date) else result
        except (TypeError, ValueError, OverflowError) as error:
            raise FormulaError(str(error)) from error
