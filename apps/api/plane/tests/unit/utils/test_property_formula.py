# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import datetime
import typing as t

import pytest

import plane.utils.property_formula as property_formula

pytestmark: pytest.MarkDecorator = pytest.mark.unit

NOW: datetime.datetime = datetime.datetime(2026, 10, 6, 14, 0, tzinfo=datetime.timezone.utc)


@pytest.mark.parametrize(
    ("expression", "values", "expected"),
    [
        ("1+2*3", {}, 7),
        ("(1+2)*3", {}, 9),
        ("-{{points}} + 10", {"points": 4}, 6),
        ("7 / 2", {}, 3.5),
        ("ROUND(12.345, 2)", {}, 12.35),
        ("ABS(-4)", {}, 4),
        ('"Sprint " & 3', {}, "Sprint 3"),
        ("1 & 2", {}, "12"),
        ("CONCAT('a', 1, 2.5)", {}, "a12.5"),
        ('UPPER({{Some Field}}) & "!"', {"some_field": "ok"}, "OK!"),
        ("LEN(CONCAT(LOWER('AB'), 'C')) = 3", {}, True),
        ("IF(false, 1/0, 4)", {}, 4),
        ("IF({{done}}, 'yes', 'no')", {"done": True}, "yes"),
        ("{{left}} < {{right}}", {"left": 1, "right": 2}, True),
        ("{{left}} < {{right}}", {"left": "first", "right": "second"}, True),
        ("{{left}} >= {{right}}", {"left": datetime.date(2026, 10, 6), "right": datetime.date(2026, 10, 7)}, False),
        ("{{left}} != {{right}}", {"left": "a", "right": "b"}, True),
        ("TODAY()+3", {}, "2026-10-09"),
        ("{{due_date}} - 1", {"due_date": datetime.date(2026, 10, 10)}, "2026-10-09"),
        ("{{due date}}-TODAY()", {"due_date": datetime.date(2026, 10, 10)}, 4),
        ("NOW() - {{start_date}}", {"start_date": datetime.date(2026, 10, 4)}, 2),
        ("TODAY() < NOW()", {}, True),
        ("{{start_date}} = NOW()", {"start_date": datetime.date(2026, 10, 6)}, False),
    ],
)
def test_expression_evaluates_to(
    expression: str, values: t.Dict[str, property_formula.FormulaValue], expected: property_formula.JsonValue
) -> None:
    actual: property_formula.JsonValue = property_formula.Formula(expression).evaluate(values, NOW)
    assert (actual, type(actual)) == (expected, type(expected))


@pytest.mark.parametrize(
    "expression",
    ["{{empty}} + 2", "-{{empty}}", "{{empty}} = 1", "UPPER({{empty}})", "IF({{empty}}, 1, 2)", "{{empty}} & 'x'"],
)
def test_empty_source_makes_the_result_empty(expression: str) -> None:
    assert property_formula.Formula(expression).evaluate({"empty": None}, NOW) is None


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ("1 +", "Expression ended unexpectedly."),
        ("1 2", "Unexpected expression token."),
        ("(1 + 2", "Expression ended unexpectedly."),
        ("1 ? 2", "Invalid expression at character 2."),
        ("SUM(1, 2)", "Unknown function or token: SUM."),
        ("ABS 1", "Functions require parentheses."),
        ("IF(true, 1)", "IF takes 3 to 3 arguments."),
        (r'"\x"', "Invalid string literal"),
        (r'"\u123"', "Invalid string literal"),
    ],
)
def test_expression_that_does_not_parse_is_refused(expression: str, message: str) -> None:
    with pytest.raises(property_formula.FormulaError, match=message.replace("(", r"\(").replace("?", r"\?")):
        property_formula.Formula(expression)


@pytest.mark.parametrize(
    ("expression", "values", "message"),
    [
        ("1 / 0", {}, "Division by zero."),
        ("{{renamed}} + 1", {}, "Unknown property: renamed."),
        ("{{text}} + 1", {"text": "a"}, "Expected a finite number."),
        ("UPPER(1)", {}, "UPPER requires text."),
        ("ROUND(1.5, 0.5)", {}, "ROUND precision must be a whole number."),
        ("{{date}} * 2", {"date": datetime.date(2026, 10, 6)}, "Dates support subtraction or whole-day offsets."),
        ("{{text}} < 1", {"text": "a"}, "'<' not supported between instances of 'str' and 'int'"),
    ],
)
def test_expression_that_cannot_be_evaluated_reports_why(
    expression: str, values: t.Dict[str, property_formula.FormulaValue], message: str
) -> None:
    error: pytest.ExceptionInfo[property_formula.FormulaError]
    with pytest.raises(property_formula.FormulaError) as error:
        property_formula.Formula(expression).evaluate(values, NOW)
    assert str(error.value) == message


def test_references_are_normalized_names() -> None:
    assert property_formula.Formula("{{ Story Points }} + {{due_date}} + {{DUE   DATE}}").references == {
        "story_points",
        "due_date",
    }
