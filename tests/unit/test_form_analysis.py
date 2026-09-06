"""Turning page source into normalized fields."""

from __future__ import annotations

from pathlib import Path

import pytest
from jobapply_browser.forms import analyze_html
from jobapply_shared.enums import FieldType

SITES = Path(__file__).parent.parent / "mock_ats" / "sites"


def test_greenhouse_form_is_fully_described():
    spec = analyze_html(
        (SITES / "greenhouse.html").read_text(),
        url="https://boards.greenhouse.io/acme/jobs/1",
    )
    fields = {field.field_id: field for field in spec.fields}

    assert set(fields) == {
        "first_name",
        "last_name",
        "email",
        "phone",
        "linkedin",
        "resume",
        "work_auth",
        "sponsorship",
    }
    assert fields["email"].type == FieldType.EMAIL
    assert fields["phone"].type == FieldType.PHONE
    assert fields["resume"].type == FieldType.FILE
    assert fields["work_auth"].type == FieldType.SELECT
    assert [option.label for option in fields["work_auth"].options] == [
        "Please select",
        "Yes",
        "No",
    ]
    assert fields["first_name"].required is True
    assert fields["phone"].required is False
    assert spec.page_title == "Data Engineer — Northwind Analytics"


def test_required_is_read_from_the_attribute_and_from_a_starred_label():
    spec = analyze_html(
        "<form>"
        "<label for='a'>Name *</label><input id='a'>"
        "<label for='b'>Nickname</label><input id='b'>"
        "<label for='c'>Email</label><input id='c' required>"
        "</form>"
    )
    fields = {field.field_id: field for field in spec.fields}
    assert fields["a"].required is True
    assert fields["a"].label == "Name", "the marker is not part of the label"
    assert fields["b"].required is False
    assert fields["c"].required is True


def test_hidden_and_button_inputs_are_ignored():
    spec = analyze_html(
        "<form><input type='hidden' name='csrf'><input name='real'>"
        "<input type='submit' value='Go'></form>"
    )
    assert [field.field_id for field in spec.fields] == ["real"]
    assert spec.submit_selector == "input[type='submit']"


def test_a_radio_group_is_one_question_with_options():
    spec = analyze_html(
        "<form><p>Will you require sponsorship?</p>"
        "<input type='radio' name='sponsor' value='yes' required><label>Yes</label>"
        "<input type='radio' name='sponsor' value='no'><label>No</label></form>"
    )
    assert len(spec.fields) == 1
    field = spec.fields[0]
    assert field.type == FieldType.RADIO
    assert field.required is True
    assert field.question == "Will you require sponsorship?"
    assert [(option.label, option.value) for option in field.options] == [
        ("Yes", "yes"),
        ("No", "no"),
    ]


def test_a_wrapping_label_is_attached_to_its_control():
    spec = analyze_html("<form><label>Preferred name<input name='preferred'></label></form>")
    assert spec.fields[0].label == "Preferred name"


def test_context_does_not_leak_between_fields():
    spec = analyze_html(
        "<form><p>Question one</p><input name='a'><p>Question two</p><input name='b'></form>"
    )
    fields = {field.field_id: field for field in spec.fields}
    assert fields["a"].question == "Question one"
    assert fields["b"].question == "Question two"


def test_textarea_and_maxlength_are_captured():
    spec = analyze_html(
        "<form><label for='w'>Why?</label><textarea id='w' maxlength='500'></textarea></form>"
    )
    field = spec.fields[0]
    assert field.type == FieldType.TEXTAREA
    assert field.max_length == 500


def test_multiselect_is_distinguished_from_select():
    spec = analyze_html(
        "<form><select name='a' multiple><option>x</option></select>"
        "<select name='b'><option>y</option></select></form>"
    )
    types = {field.field_id: field.type for field in spec.fields}
    assert types["a"] == FieldType.MULTISELECT
    assert types["b"] == FieldType.SELECT


def test_selectors_prefer_id_then_name():
    spec = analyze_html("<form><input id='x' name='y'><input name='z'></form>")
    selectors = {field.field_id: field.selector for field in spec.fields}
    assert selectors["x"] == "#x"
    assert selectors["z"] == "[name='z']"


@pytest.mark.parametrize("site", ["lever.html", "generic.html", "workday.html"])
def test_every_mock_site_parses_without_error(site):
    spec = analyze_html((SITES / site).read_text())
    assert spec.fields
