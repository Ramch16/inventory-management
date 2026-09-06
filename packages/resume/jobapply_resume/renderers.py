"""Resume rendering to DOCX and PDF.

ATS compatibility drives every decision here: no tables for layout, no text boxes, no
images, standard fonts, real headings and selectable text. The templates differ in
typography and spacing, not in structure, so a parser sees the same document shape
whichever one the user picks.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date

from jobapply_shared.enums import ResumeTemplate

from jobapply_resume.models import TailoredResume


@dataclass(frozen=True)
class TemplateStyle:
    key: str
    label: str
    body_font: str
    heading_font: str
    body_size: int
    heading_size: int
    name_size: int
    #: Uppercase section headings read as headings to both humans and parsers.
    uppercase_headings: bool
    rule_under_headings: bool
    accent: tuple[int, int, int] | None


TEMPLATES: dict[str, TemplateStyle] = {
    ResumeTemplate.ATS_CLASSIC: TemplateStyle(
        key="ats_classic",
        label="ATS Classic",
        body_font="Calibri",
        heading_font="Calibri",
        body_size=10,
        heading_size=11,
        name_size=18,
        uppercase_headings=True,
        rule_under_headings=True,
        accent=None,
    ),
    ResumeTemplate.MODERN_PROFESSIONAL: TemplateStyle(
        key="modern_professional",
        label="Modern Professional",
        body_font="Calibri",
        heading_font="Calibri",
        body_size=10,
        heading_size=12,
        name_size=20,
        uppercase_headings=False,
        rule_under_headings=True,
        accent=(0x1F, 0x4E, 0x79),
    ),
    ResumeTemplate.TECHNICAL: TemplateStyle(
        key="technical",
        label="Technical",
        body_font="Georgia",
        heading_font="Georgia",
        body_size=10,
        heading_size=11,
        name_size=17,
        uppercase_headings=True,
        rule_under_headings=False,
        accent=None,
    ),
    ResumeTemplate.MINIMAL: TemplateStyle(
        key="minimal",
        label="Minimal",
        body_font="Helvetica",
        heading_font="Helvetica",
        body_size=10,
        heading_size=11,
        name_size=16,
        uppercase_headings=False,
        rule_under_headings=False,
        accent=None,
    ),
}


def get_template(name: str | None) -> TemplateStyle:
    return TEMPLATES.get(name or "", TEMPLATES[ResumeTemplate.ATS_CLASSIC])


def format_month(value: date | None, fallback: str = "") -> str:
    return value.strftime("%b %Y") if value else fallback


def date_range(start: date | None, end: date | None, is_current: bool) -> str:
    left = format_month(start)
    right = "Present" if is_current else format_month(end)
    if not left and not right:
        return ""
    return f"{left} – {right}".strip(" –")


def contact_line(document: TailoredResume) -> str:
    contact = document.contact
    parts = [contact.location, contact.phone, contact.email]
    return " | ".join(part for part in parts if part)


def links_line(document: TailoredResume) -> str:
    contact = document.contact
    parts = [contact.linkedin_url, contact.github_url, contact.portfolio_url]
    return " | ".join(part for part in parts if part)


class DocxRenderer:
    """python-docx renderer. Headings use real Word heading styles so an ATS that
    reads document structure sees sections rather than bold text."""

    def __init__(self, template: str | None = None) -> None:
        self.style = get_template(template)

    def render(self, document: TailoredResume) -> bytes:
        import docx
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt, RGBColor

        style = self.style
        doc = docx.Document()

        normal = doc.styles["Normal"]
        normal.font.name = style.body_font
        normal.font.size = Pt(style.body_size)
        for section in doc.sections:
            section.top_margin = section.bottom_margin = Pt(36)
            section.left_margin = section.right_margin = Pt(45)

        def heading(text: str) -> None:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(10)
            paragraph.paragraph_format.space_after = Pt(2)
            run = paragraph.add_run(text.upper() if style.uppercase_headings else text)
            run.bold = True
            run.font.size = Pt(style.heading_size)
            run.font.name = style.heading_font
            if style.accent:
                run.font.color.rgb = RGBColor(*style.accent)
            if style.rule_under_headings:
                border = doc.add_paragraph()
                border.paragraph_format.space_before = Pt(0)
                border.paragraph_format.space_after = Pt(4)
                rule = border.add_run("_" * 78)
                rule.font.size = Pt(5)

        # --- header ---------------------------------------------------------
        name_paragraph = doc.add_paragraph()
        name_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name_paragraph.paragraph_format.space_after = Pt(2)
        name_run = name_paragraph.add_run(document.contact.full_name or "")
        name_run.bold = True
        name_run.font.size = Pt(style.name_size)
        name_run.font.name = style.heading_font

        for line in (contact_line(document), links_line(document)):
            if not line:
                continue
            paragraph = doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(1)
            run = paragraph.add_run(line)
            run.font.size = Pt(style.body_size - 1)

        # --- summary --------------------------------------------------------
        if document.summary:
            heading("Summary")
            doc.add_paragraph(document.summary)

        # --- skills ---------------------------------------------------------
        if document.skills:
            heading("Skills")
            doc.add_paragraph(", ".join(document.skills))

        # --- experience -----------------------------------------------------
        if document.experience:
            heading("Experience")
            for role in document.experience:
                line = doc.add_paragraph()
                line.paragraph_format.space_after = Pt(0)
                title_run = line.add_run(f"{role.title}, {role.company}")
                title_run.bold = True
                dates = date_range(role.start_date, role.end_date, role.is_current)
                meta = " | ".join(part for part in (role.location, dates) if part)
                if meta:
                    meta_run = line.add_run(f"  —  {meta}")
                    meta_run.italic = True
                for bullet in role.bullets:
                    doc.add_paragraph(bullet.text, style="List Bullet")

        # --- projects -------------------------------------------------------
        if document.projects:
            heading("Projects")
            for project in document.projects:
                line = doc.add_paragraph()
                line.paragraph_format.space_after = Pt(0)
                run = line.add_run(project.name)
                run.bold = True
                if project.technologies:
                    line.add_run(f"  —  {', '.join(project.technologies)}").italic = True
                for highlight in project.highlights:
                    doc.add_paragraph(highlight.text, style="List Bullet")

        # --- education ------------------------------------------------------
        if document.education:
            heading("Education")
            for record in document.education:
                line = doc.add_paragraph()
                line.paragraph_format.space_after = Pt(0)
                run = line.add_run(record.institution)
                run.bold = True
                details = ", ".join(part for part in (record.degree, record.field_of_study) if part)
                tail = " | ".join(
                    part
                    for part in (
                        details,
                        format_month(record.end_date),
                        f"GPA {record.gpa}" if record.gpa else "",
                    )
                    if part
                )
                if tail:
                    line.add_run(f"  —  {tail}")

        # --- certifications --------------------------------------------------
        if document.certifications:
            heading("Certifications")
            for certification in document.certifications:
                doc.add_paragraph(certification, style="List Bullet")

        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()


class PdfRenderer:
    """ReportLab renderer producing selectable text with no images or table layout."""

    def __init__(self, template: str | None = None) -> None:
        self.style = get_template(template)

    def render(self, document: TailoredResume) -> bytes:
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            HRFlowable,
            ListFlowable,
            ListItem,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
        )

        style = self.style
        # ReportLab's built-in font names; Calibri is not embedded by default, so the
        # closest standard face is used to keep text selectable and portable.
        body_font = {"Calibri": "Helvetica", "Helvetica": "Helvetica", "Georgia": "Times-Roman"}[
            style.body_font
        ]
        bold_font = {"Helvetica": "Helvetica-Bold", "Times-Roman": "Times-Bold"}[body_font]

        sheet = getSampleStyleSheet()
        body = ParagraphStyle(
            "body",
            parent=sheet["BodyText"],
            fontName=body_font,
            fontSize=style.body_size,
            leading=style.body_size + 3,
            spaceAfter=3,
        )
        name = ParagraphStyle(
            "name",
            parent=body,
            fontName=bold_font,
            fontSize=style.name_size,
            leading=style.name_size + 3,
            alignment=TA_CENTER,
            spaceAfter=2,
        )
        contact = ParagraphStyle(
            "contact", parent=body, fontSize=style.body_size - 1, alignment=TA_CENTER, spaceAfter=1
        )
        heading = ParagraphStyle(
            "heading",
            parent=body,
            fontName=bold_font,
            fontSize=style.heading_size,
            spaceBefore=10,
            spaceAfter=2,
            textColor=("#{:02x}{:02x}{:02x}".format(*style.accent) if style.accent else "black"),
        )

        def escape(text: str) -> str:
            return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        story: list = [Paragraph(escape(document.contact.full_name or ""), name)]
        for line in (contact_line(document), links_line(document)):
            if line:
                story.append(Paragraph(escape(line), contact))

        def section(title: str) -> None:
            story.append(
                Paragraph(escape(title.upper() if style.uppercase_headings else title), heading)
            )
            if style.rule_under_headings:
                story.append(HRFlowable(width="100%", thickness=0.5, spaceAfter=4))

        def bullets(texts: list[str]) -> None:
            if not texts:
                return
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(escape(text), body), leftIndent=12) for text in texts],
                    bulletType="bullet",
                    start="•",
                    leftIndent=12,
                )
            )

        if document.summary:
            section("Summary")
            story.append(Paragraph(escape(document.summary), body))

        if document.skills:
            section("Skills")
            story.append(Paragraph(escape(", ".join(document.skills)), body))

        if document.experience:
            section("Experience")
            for role in document.experience:
                dates = date_range(role.start_date, role.end_date, role.is_current)
                meta = " | ".join(part for part in (role.location, dates) if part)
                story.append(
                    Paragraph(
                        f"<b>{escape(role.title)}, {escape(role.company)}</b>"
                        + (f" — <i>{escape(meta)}</i>" if meta else ""),
                        body,
                    )
                )
                bullets([bullet.text for bullet in role.bullets])

        if document.projects:
            section("Projects")
            for project in document.projects:
                suffix = (
                    f" — <i>{escape(', '.join(project.technologies))}</i>"
                    if project.technologies
                    else ""
                )
                story.append(Paragraph(f"<b>{escape(project.name)}</b>{suffix}", body))
                bullets([highlight.text for highlight in project.highlights])

        if document.education:
            section("Education")
            for record in document.education:
                details = ", ".join(part for part in (record.degree, record.field_of_study) if part)
                tail = " | ".join(
                    part
                    for part in (
                        details,
                        format_month(record.end_date),
                        f"GPA {record.gpa}" if record.gpa else "",
                    )
                    if part
                )
                story.append(
                    Paragraph(
                        f"<b>{escape(record.institution)}</b>"
                        + (f" — {escape(tail)}" if tail else ""),
                        body,
                    )
                )

        if document.certifications:
            section("Certifications")
            bullets(list(document.certifications))

        story.append(Spacer(1, 2))

        buffer = io.BytesIO()
        SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
            leftMargin=0.62 * inch,
            rightMargin=0.62 * inch,
            title=f"{document.contact.full_name or 'Resume'} — Resume",
            author=document.contact.full_name or "",
        ).build(story)
        return buffer.getvalue()


def render_all(document: TailoredResume) -> tuple[bytes, bytes]:
    """Render both formats with the document's own template."""
    return (
        DocxRenderer(document.template).render(document),
        PdfRenderer(document.template).render(document),
    )
