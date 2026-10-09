# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import datetime
import typing as t

import pytest

import plane.db.models as db_models
import plane.utils.custom_properties as custom_properties
import plane.utils.property_formula as property_formula

pytestmark: pytest.MarkDecorator = pytest.mark.unit


@pytest.mark.parametrize(
    ("property_fields", "stored", "expected"),
    [
        ({"property_type": "TEXT", "settings": {"display_format": "single-line"}}, "abc", "abc"),
        (
            {"property_type": "TEXT", "settings": {"display_format": "readonly"}, "default_value": ["Fixed"]},
            None,
            "Fixed",
        ),
        ({"property_type": "TEXT", "settings": {"display_format": "readonly"}}, None, None),
        ({"property_type": "DECIMAL"}, 2.5, 2.5),
        ({"property_type": "DECIMAL"}, None, None),
        ({"property_type": "BOOLEAN"}, True, True),
        ({"property_type": "BOOLEAN"}, None, False),
        ({"property_type": "DATETIME"}, "2026-10-06", datetime.date(2026, 10, 6)),
        ({"property_type": "DATETIME"}, None, None),
    ],
)
def test_formula_reads_a_property_by_its_normalized_name(
    property_fields: t.Dict[str, t.Any], stored: property_formula.JsonValue, expected: property_formula.FormulaValue
) -> None:
    property: db_models.IssueProperty = db_models.IssueProperty(display_name="Story  Points", **property_fields)
    values: custom_properties.PropertyValues = {} if stored is None else {str(property.id): stored}

    assert custom_properties.get_formula_sources([property], values) == {"story_points": expected}


@pytest.mark.parametrize(
    "property_fields",
    [
        {"property_type": "URL"},
        {"property_type": "OPTION"},
        {"property_type": "RELATION", "relation_type": "USER"},
        {"property_type": "RELATION", "relation_type": "RICH_TEXT"},
        {"property_type": "FORMULA", "settings": {"expression": "1"}},
    ],
)
def test_formula_reads_text_number_date_and_boolean_properties_only(property_fields: t.Dict[str, t.Any]) -> None:
    property: db_models.IssueProperty = db_models.IssueProperty(display_name="Source", **property_fields)

    assert custom_properties.get_formula_sources([property], {str(property.id): "x"}) == {}


def test_formula_payload_has_a_value_or_an_error_for_every_formula() -> None:
    points: db_models.IssueProperty = db_models.IssueProperty(display_name="Points", property_type="DECIMAL")
    doubled: db_models.IssueProperty = db_models.IssueProperty(
        display_name="Doubled", property_type="FORMULA", settings={"expression": "{{points}} * 2"}
    )
    broken: db_models.IssueProperty = db_models.IssueProperty(
        display_name="Broken", property_type="FORMULA", settings={"expression": "{{gone}} + 1"}
    )

    actual: t.Dict[str, t.Dict[str, property_formula.JsonValue]] = custom_properties.get_formula_payload(
        [points, doubled, broken], {str(points.id): 4}
    )

    assert actual == {
        "formula_values": {str(doubled.id): 8, str(broken.id): None},
        "formula_errors": {str(broken.id): "Unknown property: gone."},
    }
