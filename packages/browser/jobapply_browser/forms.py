"""Form analysis: a rendered page becomes a list of ``NormalizedField``.

Two entry points share one implementation: ``analyze_html`` works on page source and
is what the unit tests exercise, while ``analyze_page`` runs the same extraction
against a live Playwright page. Keeping the logic in one place means the browser path
cannot drift from the tested one.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from jobapply_shared.enums import AtsKind, FieldType

from jobapply_browser.models import FieldOption, FormSpec, NormalizedField

INPUT_TYPE_MAP: dict[str, FieldType] = {
    "text": FieldType.TEXT,
    "email": FieldType.EMAIL,
    "tel": FieldType.PHONE,
    "url": FieldType.URL,
    "number": FieldType.NUMBER,
    "date": FieldType.DATE,
    "file": FieldType.FILE,
    "radio": FieldType.RADIO,
    "checkbox": FieldType.CHECKBOX,
    "search": FieldType.TEXT,
    "password": FieldType.TEXT,
}

#: Controls that are never part of an application's content.
IGNORED_INPUT_TYPES = {"hidden", "submit", "button", "reset", "image"}

_WS_RE = re.compile(r"\s+")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = _WS_RE.sub(" ", re.sub(r"<[^>]+>", " ", value)).strip()
    return text or None


class _FormParser(HTMLParser):
    """Minimal DOM walk that keeps enough context to attach labels to controls."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.controls: list[dict[str, Any]] = []
        self.labels: dict[str, str] = {}
        self.submit_selector: str | None = None
        self.title: str | None = None

        self._in_label = False
        self._label_for: str | None = None
        self._label_text: list[str] = []
        self._in_title = False
        self._select: dict[str, Any] | None = None
        self._option: dict[str, Any] | None = None
        self._textarea: dict[str, Any] | None = None
        #: Recent visible text, used when a control has no <label>.
        self._recent_text: list[str] = []

    # -- helpers ----------------------------------------------------------
    def _attrs(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key.lower(): (value or "") for key, value in attrs}

    def _context(self) -> str | None:
        """Visible text since the previous control.

        Resetting after each control keeps one field's question from leaking into the
        next one's context.
        """
        text = _clean(" ".join(self._recent_text[-4:]))
        self._recent_text = []
        return text

    # -- tags -------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = self._attrs(attrs)

        if tag == "title":
            self._in_title = True
            return

        if tag == "label":
            self._in_label = True
            self._label_for = attributes.get("for") or None
            self._label_text = []
            return

        if tag == "input":
            input_type = (attributes.get("type") or "text").lower()
            if input_type in IGNORED_INPUT_TYPES:
                if input_type == "submit" and self.submit_selector is None:
                    self.submit_selector = "input[type='submit']"
                return
            self.controls.append(
                {
                    "tag": "input",
                    "type": INPUT_TYPE_MAP.get(input_type, FieldType.TEXT),
                    "attrs": attributes,
                    "context": self._context(),
                    "options": [],
                }
            )
            return

        if tag == "textarea":
            self._textarea = {
                "tag": "textarea",
                "type": FieldType.TEXTAREA,
                "attrs": attributes,
                "context": self._context(),
                "options": [],
            }
            return

        if tag == "select":
            self._select = {
                "tag": "select",
                "type": FieldType.MULTISELECT if "multiple" in attributes else FieldType.SELECT,
                "attrs": attributes,
                "context": self._context(),
                "options": [],
            }
            return

        if tag == "option" and self._select is not None:
            self._option = {"value": attributes.get("value"), "label": []}
            return

        if (
            tag == "button"
            and self.submit_selector is None
            and attributes.get("type", "submit") == "submit"
        ):
            self.submit_selector = "button[type='submit']"

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "label":
            self._in_label = False
            text = _clean(" ".join(self._label_text))
            if self._label_for and text:
                self.labels[self._label_for] = text
            elif text:
                # A wrapping <label> with no "for": attach it to the last control.
                for control in reversed(self.controls):
                    if control.get("label") is None:
                        control["label"] = text
                        break
            self._label_for = None
            self._label_text = []
        elif tag == "textarea" and self._textarea is not None:
            self.controls.append(self._textarea)
            self._textarea = None
        elif tag == "option" and self._option is not None and self._select is not None:
            label = _clean(" ".join(self._option["label"])) or ""
            value = self._option["value"]
            self._select["options"].append(
                FieldOption(label=label, value=value if value is not None else label)
            )
            self._option = None
        elif tag == "select" and self._select is not None:
            self.controls.append(self._select)
            self._select = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = (self.title or "") + text
        elif self._in_label:
            self._label_text.append(text)
        elif self._option is not None:
            self._option["label"].append(text)
        else:
            # Nearby prose is kept as context for controls that have no label at all.
            self._recent_text.append(text)


def _selector_for(attrs: dict[str, str], index: int) -> str:
    if attrs.get("id"):
        return f"#{attrs['id']}"
    if attrs.get("name"):
        return f"[name='{attrs['name']}']"
    return f"form *:nth-of-type({index + 1})"


def _field_id(attrs: dict[str, str], index: int) -> str:
    return attrs.get("id") or attrs.get("name") or f"field_{index}"


def _is_required(attrs: dict[str, str], label: str | None) -> bool:
    if "required" in attrs or attrs.get("aria-required") == "true":
        return True
    return bool(label and label.rstrip().endswith("*"))


def build_fields(controls: list[dict[str, Any]], labels: dict[str, str]) -> list[NormalizedField]:
    fields: list[NormalizedField] = []
    #: Radio groups share a name; they are one question, not one per option.
    seen_radio_groups: dict[str, NormalizedField] = {}

    for index, control in enumerate(controls):
        attrs = control["attrs"]
        label = control.get("label") or labels.get(attrs.get("id", "")) or None
        label = _clean(label)
        field_type: FieldType = control["type"]

        if field_type == FieldType.RADIO and attrs.get("name"):
            group = seen_radio_groups.get(attrs["name"])
            option = FieldOption(
                label=label or attrs.get("value", ""), value=attrs.get("value", label or "")
            )
            if group is not None:
                group.options.append(option)
                continue
            field = NormalizedField(
                field_id=attrs["name"],
                label=None,
                name=attrs.get("name"),
                dom_id=attrs.get("id") or None,
                type=FieldType.RADIO,
                required=_is_required(attrs, label),
                options=[option],
                context_text=control.get("context"),
                question=_clean(control.get("context")),
                selector=f"[name='{attrs['name']}']",
            )
            seen_radio_groups[attrs["name"]] = field
            fields.append(field)
            continue

        clean_label = label.rstrip(" *") if label else None
        fields.append(
            NormalizedField(
                field_id=_field_id(attrs, index),
                label=clean_label,
                name=attrs.get("name") or None,
                dom_id=attrs.get("id") or None,
                type=field_type,
                required=_is_required(attrs, label),
                options=control.get("options") or [],
                placeholder=_clean(attrs.get("placeholder")),
                context_text=control.get("context"),
                max_length=int(attrs["maxlength"])
                if attrs.get("maxlength", "").isdigit()
                else None,
                question=clean_label or _clean(control.get("context")),
                selector=_selector_for(attrs, index),
            )
        )
    return fields


def analyze_html(html: str, *, url: str = "", ats: AtsKind = AtsKind.UNKNOWN) -> FormSpec:
    parser = _FormParser()
    parser.feed(html)
    return FormSpec(
        url=url,
        ats=ats,
        fields=build_fields(parser.controls, parser.labels),
        submit_selector=parser.submit_selector,
        page_title=_clean(parser.title),
    )


async def analyze_page(page: Any, *, ats: AtsKind = AtsKind.UNKNOWN) -> FormSpec:
    """Analyse a live Playwright page using the same extraction as ``analyze_html``."""
    html = await page.content()
    spec = analyze_html(html, url=page.url, ats=ats)
    spec.page_title = spec.page_title or await page.title()
    return spec
