import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    KeepTogether,
)


# ==========================================================
# CONFIGURATION
# ==========================================================

OUTPUT_DIR = "data/generated_resumes"


def _safe_text(value):
    """
    Convert a value into safe printable text.
    """

    if value is None:
        return ""

    return str(value).strip()


def _safe_filename(value):
    """
    Convert company/position names into safe filenames.
    """

    value = _safe_text(value)

    value = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        value,
    )

    return value.strip("_")


def _escape(value):
    """
    Escape characters that ReportLab Paragraph
    interprets as markup.
    """

    value = _safe_text(value)

    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ==========================================================
# STYLES
# ==========================================================

def _build_styles():

    base = getSampleStyleSheet()

    return {
        "name": ParagraphStyle(
            "ResumeName",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=21,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),

        "contact": ParagraphStyle(
            "ResumeContact",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),

        "section": ParagraphStyle(
            "ResumeSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            spaceBefore=7,
            spaceAfter=3,
        ),

        "normal": ParagraphStyle(
            "ResumeNormal",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=3,
        ),

        "item_title": ParagraphStyle(
            "ResumeItemTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            spaceAfter=1,
        ),

        "meta": ParagraphStyle(
            "ResumeMeta",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=11,
            spaceAfter=2,
        ),

        "bullet": ParagraphStyle(
            "ResumeBullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=11.5,
            leftIndent=10,
            firstLineIndent=-6,
            spaceAfter=2,
        ),
    }


# ==========================================================
# SECTION HELPERS
# ==========================================================

def _section_heading(story, title, styles):

    story.append(
        Paragraph(
            _escape(title.upper()),
            styles["section"],
        )
    )

    story.append(
        HRFlowable(
            width="100%",
            thickness=0.6,
            color=colors.black,
            spaceBefore=0,
            spaceAfter=4,
        )
    )


def _add_bullet(story, text, styles):

    text = _safe_text(text)

    if not text:
        return

    story.append(
        Paragraph(
            f"• {_escape(text)}",
            styles["bullet"],
        )
    )


# ==========================================================
# HEADER
# ==========================================================

def _render_header(story, resume, styles):

    candidate = resume.get(
        "candidate",
        {},
    )

    links = resume.get(
        "professional_links",
        {},
    )

    name = candidate.get(
        "full_name",
        "",
    )

    story.append(
        Paragraph(
            _escape(name),
            styles["name"],
        )
    )

    contact_parts = []

    for value in [
        candidate.get("email"),
        candidate.get("phone"),
        candidate.get("location"),
    ]:

        value = _safe_text(value)

        if value:
            contact_parts.append(value)

    if contact_parts:

        story.append(
            Paragraph(
                _escape(
                    " | ".join(contact_parts)
                ),
                styles["contact"],
            )
        )

    link_parts = []

    for label, key in [
        ("GitHub", "github"),
        ("LinkedIn", "linkedin"),
        ("Portfolio", "portfolio"),
    ]:

        value = _safe_text(
            links.get(key)
        )

        if value:

            link_parts.append(
                f"{label}: {value}"
            )

    if link_parts:

        story.append(
            Paragraph(
                _escape(
                    " | ".join(link_parts)
                ),
                styles["contact"],
            )
        )

    story.append(
        Spacer(
            1,
            3,
        )
    )


# ==========================================================
# SUMMARY
# ==========================================================

def _render_summary(story, resume, styles):

    summary = _safe_text(
        resume.get(
            "summary"
        )
    )

    if not summary:
        return

    _section_heading(
        story,
        "Professional Summary",
        styles,
    )

    story.append(
        Paragraph(
            _escape(summary),
            styles["normal"],
        )
    )


# ==========================================================
# SKILLS
# ==========================================================

def _render_skills(story, resume, styles):

    skills = resume.get(
        "skills",
        [],
    )

    if not isinstance(
        skills,
        list,
    ):
        return

    skills = [
        _safe_text(skill)
        for skill in skills
        if _safe_text(skill)
    ]

    if not skills:
        return

    _section_heading(
        story,
        "Technical Skills",
        styles,
    )

    story.append(
        Paragraph(
            _escape(
                " • ".join(skills)
            ),
            styles["normal"],
        )
    )


# ==========================================================
# EXPERIENCE
# ==========================================================

def _render_experience(story, resume, styles):

    experience = resume.get(
        "experience",
        [],
    )

    if not isinstance(
        experience,
        list,
    ) or not experience:

        return

    _section_heading(
        story,
        "Experience",
        styles,
    )

    for item in experience:

        if not isinstance(
            item,
            dict,
        ):
            continue

        role = _safe_text(
            item.get("role")
        )

        company = _safe_text(
            item.get("company")
        )

        title_parts = [
            value
            for value in [
                role,
                company,
            ]
            if value
        ]

        block = []

        if title_parts:

            block.append(
                Paragraph(
                    _escape(
                        " — ".join(
                            title_parts
                        )
                    ),
                    styles["item_title"],
                )
            )

        meta = []

        start = _safe_text(
            item.get(
                "start_date"
            )
        )

        end = _safe_text(
            item.get(
                "end_date"
            )
        )

        location = _safe_text(
            item.get(
                "location"
            )
        )

        if start or end:

            meta.append(
                f"{start} - {end}".strip(
                    " -"
                )
            )

        if location:
            meta.append(location)

        if meta:

            block.append(
                Paragraph(
                    _escape(
                        " | ".join(meta)
                    ),
                    styles["meta"],
                )
            )

        story.extend(block)

        responsibilities = item.get(
            "responsibilities",
            [],
        )

        if isinstance(
            responsibilities,
            list,
        ):

            for responsibility in responsibilities:

                _add_bullet(
                    story,
                    responsibility,
                    styles,
                )

        story.append(
            Spacer(
                1,
                3,
            )
        )


# ==========================================================
# PROJECTS
# ==========================================================

def _render_projects(story, resume, styles):

    projects = resume.get(
        "projects",
        [],
    )

    if not isinstance(
        projects,
        list,
    ) or not projects:

        return

    _section_heading(
        story,
        "Projects",
        styles,
    )

    for project in projects:

        if not isinstance(
            project,
            dict,
        ):
            continue

        name = _safe_text(
            project.get(
                "name"
            )
        )

        technologies = project.get(
            "technologies",
            [],
        )

        description = _safe_text(
            project.get(
                "description"
            )
        )

        block = []

        if name:

            block.append(
                Paragraph(
                    _escape(name),
                    styles["item_title"],
                )
            )

        if isinstance(
            technologies,
            list,
        ):

            technologies = [
                _safe_text(value)
                for value in technologies
                if _safe_text(value)
            ]

            if technologies:

                block.append(
                    Paragraph(
                        "<b>Technologies:</b> "
                        + _escape(
                            ", ".join(
                                technologies
                            )
                        ),
                        styles["normal"],
                    )
                )

        if description:

            block.append(
                Paragraph(
                    _escape(description),
                    styles["normal"],
                )
            )

        if block:

            story.append(
                KeepTogether(block)
            )

            story.append(
                Spacer(
                    1,
                    3,
                )
            )


# ==========================================================
# EDUCATION
# ==========================================================

def _render_education(story, resume, styles):

    education = resume.get(
        "education",
        [],
    )

    if not isinstance(
        education,
        list,
    ) or not education:

        return

    _section_heading(
        story,
        "Education",
        styles,
    )

    for item in education:

        if not isinstance(
            item,
            dict,
        ):
            continue

        degree = _safe_text(
            item.get("degree")
        )

        field = _safe_text(
            item.get("field")
        )

        institution = _safe_text(
            item.get("institution")
        )

        degree_line = degree

        if field:

            if degree_line:
                degree_line += f" in {field}"
            else:
                degree_line = field

        if degree_line:

            story.append(
                Paragraph(
                    _escape(degree_line),
                    styles["item_title"],
                )
            )

        details = []

        if institution:
            details.append(institution)

        location = _safe_text(
            item.get("location")
        )

        if location:
            details.append(location)

        if details:

            story.append(
                Paragraph(
                    _escape(
                        " | ".join(details)
                    ),
                    styles["normal"],
                )
            )

        dates = []

        start_year = _safe_text(
            item.get(
                "start_year"
            )
        )

        end_year = _safe_text(
            item.get(
                "end_year"
            )
        )

        if start_year or end_year:

            dates.append(
                f"{start_year} - {end_year}".strip(
                    " -"
                )
            )

        cgpa = _safe_text(
            item.get("cgpa")
        )

        if cgpa:
            dates.append(
                f"CGPA: {cgpa}"
            )

        if dates:

            story.append(
                Paragraph(
                    _escape(
                        " | ".join(dates)
                    ),
                    styles["meta"],
                )
            )

        coursework = item.get(
            "coursework",
            [],
        )

        if isinstance(
            coursework,
            list,
        ):

            coursework = [
                _safe_text(value)
                for value in coursework
                if _safe_text(value)
            ]

            if coursework:

                story.append(
                    Paragraph(
                        "<b>Relevant Coursework:</b> "
                        + _escape(
                            ", ".join(
                                coursework
                            )
                        ),
                        styles["normal"],
                    )
                )


# ==========================================================
# CERTIFICATIONS
# ==========================================================

def _render_certifications(
    story,
    resume,
    styles,
):

    certifications = resume.get(
        "certifications",
        [],
    )

    if not isinstance(
        certifications,
        list,
    ) or not certifications:

        return

    _section_heading(
        story,
        "Certifications",
        styles,
    )

    for certification in certifications:

        _add_bullet(
            story,
            certification,
            styles,
        )


# ==========================================================
# ACHIEVEMENTS
# ==========================================================

def _render_achievements(
    story,
    resume,
    styles,
):

    achievements = resume.get(
        "achievements",
        [],
    )

    if not isinstance(
        achievements,
        list,
    ) or not achievements:

        return

    _section_heading(
        story,
        "Achievements",
        styles,
    )

    for achievement in achievements:

        _add_bullet(
            story,
            achievement,
            styles,
        )


# ==========================================================
# PDF GENERATOR
# ==========================================================

def render_resume_pdf(
    resume,
    output_path=None,
):
    """
    Convert validated resume JSON into a PDF.

    This function does NOT modify resume facts.
    It only renders the supplied content.
    """

    if not isinstance(
        resume,
        dict,
    ):
        raise ValueError(
            "Resume must be a dictionary."
        )

    candidate = resume.get(
        "candidate",
        {},
    )

    target = resume.get(
        "target",
        {},
    )

    if output_path is None:

        os.makedirs(
            OUTPUT_DIR,
            exist_ok=True,
        )

        candidate_name = _safe_filename(
            candidate.get(
                "full_name",
                "candidate",
            )
        )

        company = _safe_filename(
            target.get(
                "company",
                "company",
            )
        )

        position = _safe_filename(
            target.get(
                "position",
                "role",
            )
        )

        filename = (
            f"{candidate_name}_"
            f"{company}_"
            f"{position}.pdf"
        )

        output_path = os.path.join(
            OUTPUT_DIR,
            filename,
        )

    else:

        parent = os.path.dirname(
            output_path
        )

        if parent:

            os.makedirs(
                parent,
                exist_ok=True,
            )

    styles = _build_styles()

    document = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=(
            f"{_safe_text(candidate.get('full_name'))} Resume"
        ),
        author=_safe_text(
            candidate.get(
                "full_name"
            )
        ),
    )

    story = []

    _render_header(
        story,
        resume,
        styles,
    )

    _render_summary(
        story,
        resume,
        styles,
    )

    _render_skills(
        story,
        resume,
        styles,
    )

    _render_experience(
        story,
        resume,
        styles,
    )

    _render_projects(
        story,
        resume,
        styles,
    )

    _render_education(
        story,
        resume,
        styles,
    )

    _render_certifications(
        story,
        resume,
        styles,
    )

    _render_achievements(
        story,
        resume,
        styles,
    )

    document.build(
        story
    )

    return {
        "status": "success",
        "path": output_path,
    }