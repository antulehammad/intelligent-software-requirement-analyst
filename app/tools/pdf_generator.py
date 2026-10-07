"""
PDF Report Generator for Intelligent Software Requirement Analyst.
Generates an elegant, publication-quality A4 PDF report from FinalAnalysisResult.
"""

import io
import html
from datetime import datetime
from typing import Union, Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    Preformatted,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.models.schemas import FinalAnalysisResult


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and render exact total page count ('Page X of Y')
    along with professional header and footer rules.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(36, 808, "Intelligent Software Requirement Analysis Report — PS-2")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(36, 800, 559, 800)

        # Footer (All Pages)
        self.drawString(36, 25, "Confidential — Software Requirements & Architecture Deliverable")
        self.drawRightString(559, 25, f"Page {self._pageNumber} of {page_count}")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 35, 559, 35)

        self.restoreState()


def safe_text(val: Any) -> str:
    """Escape XML/HTML characters to prevent ReportLab parsing errors."""
    if val is None:
        return ""
    return html.escape(str(val))


def generate_pdf_report(analysis_input: Union[FinalAnalysisResult, Dict[str, Any]]) -> bytes:
    """
    Generate a professional A4 PDF report from analysis results.
    Accepts either a FinalAnalysisResult instance or a dictionary.
    Returns the PDF as raw bytes.
    """
    if isinstance(analysis_input, dict):
        analysis = FinalAnalysisResult.model_validate(analysis_input)
    else:
        analysis = analysis_input

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=50,
        bottomMargin=48,
    )

    # Base Styles
    base_styles = getSampleStyleSheet()

    # Custom Curated Styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        alignment=0,
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2563EB"),
        spaceAfter=12,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=base_styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#2563EB"),
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "BulletItem",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    callout_style = ParagraphStyle(
        "CalloutText",
        parent=base_styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E3A8A"),
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B"),
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
    )

    code_style = ParagraphStyle(
        "CodeDiagram",
        parent=base_styles["Code"],
        fontName="Courier",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#0F172A"),
    )

    story: List[Any] = []

    # ---------------------------------------------------------
    # Header Banner
    # ---------------------------------------------------------
    story.append(Paragraph("Intelligent Software Requirement Analysis Report", title_style))
    story.append(
        Paragraph(
            "<b>Domain:</b> Software Engineering &amp; AI &nbsp;|&nbsp; "
            "<b>Architecture:</b> Multi-Agent System (LangGraph) &nbsp;|&nbsp; "
            "<b>Problem Statement:</b> PS-2",
            subtitle_style,
        )
    )

    # Metadata Table
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc_source = safe_text(analysis.document_source)
    score_str = f"{analysis.validation.overall_quality_score}/10"
    status_str = safe_text(analysis.status.upper())
    fallback_info = "Yes (gemini-3.5-flash-lite)" if analysis.fallback_used else "No (gemini-3.8-flash)"

    meta_data = [
        [
            Paragraph("<b>Document Source:</b>", body_style),
            Paragraph(doc_source, body_style),
            Paragraph("<b>Generated On:</b>", body_style),
            Paragraph(timestamp, body_style),
        ],
        [
            Paragraph("<b>Quality Score:</b>", body_style),
            Paragraph(f"<b>{score_str}</b>", body_style),
            Paragraph("<b>Workflow Status:</b>", body_style),
            Paragraph(status_str, body_style),
        ],
        [
            Paragraph("<b>Fallback Model Used:</b>", body_style),
            Paragraph(fallback_info, body_style),
            Paragraph("", body_style),
            Paragraph("", body_style),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[120, 140, 110, 153])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 1. Executive Summary & System Objectives
    # ---------------------------------------------------------
    story.append(Paragraph("1. Executive Summary &amp; System Objectives", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=6))

    if analysis.requirements.summary:
        story.append(Paragraph(safe_text(analysis.requirements.summary), body_style))

    if analysis.requirements.system_goals:
        story.append(Paragraph("Key System Goals", h2_style))
        for goal in analysis.requirements.system_goals:
            story.append(Paragraph(f"• &nbsp; {safe_text(goal)}", bullet_style))

    if analysis.requirements.target_actors:
        story.append(Paragraph("Target Actors / Personas", h2_style))
        for actor in analysis.requirements.target_actors:
            story.append(Paragraph(f"• &nbsp; <b>{safe_text(actor)}</b>", bullet_style))

    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # 2. Extracted Requirements
    # ---------------------------------------------------------
    story.append(Paragraph("2. Extracted Requirements", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=6))

    # Functional Requirements Table
    story.append(Paragraph("Functional Requirements (FR)", h2_style))
    if analysis.requirements.functional_requirements:
        fr_data = [
            [
                Paragraph("<b>ID</b>", table_header_style),
                Paragraph("<b>Title</b>", table_header_style),
                Paragraph("<b>Priority</b>", table_header_style),
                Paragraph("<b>Description</b>", table_header_style),
            ]
        ]
        for req in analysis.requirements.functional_requirements:
            fr_data.append(
                [
                    Paragraph(safe_text(req.id), table_cell_bold),
                    Paragraph(safe_text(req.title), table_cell_style),
                    Paragraph(safe_text(req.priority), table_cell_style),
                    Paragraph(safe_text(req.description), table_cell_style),
                ]
            )

        fr_table = Table(fr_data, colWidths=[55, 110, 58, 300], repeatRows=1)
        fr_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F8FAFC")],
                    ),
                ]
            )
        )
        story.append(fr_table)
    else:
        story.append(Paragraph("<i>No functional requirements extracted.</i>", body_style))

    story.append(Spacer(1, 8))

    # Non-Functional Requirements Table
    story.append(Paragraph("Non-Functional Requirements (NFR)", h2_style))
    if analysis.requirements.non_functional_requirements:
        nfr_data = [
            [
                Paragraph("<b>ID</b>", table_header_style),
                Paragraph("<b>Title</b>", table_header_style),
                Paragraph("<b>Priority</b>", table_header_style),
                Paragraph("<b>Description</b>", table_header_style),
            ]
        ]
        for req in analysis.requirements.non_functional_requirements:
            nfr_data.append(
                [
                    Paragraph(safe_text(req.id), table_cell_bold),
                    Paragraph(safe_text(req.title), table_cell_style),
                    Paragraph(safe_text(req.priority), table_cell_style),
                    Paragraph(safe_text(req.description), table_cell_style),
                ]
            )

        nfr_table = Table(nfr_data, colWidths=[55, 110, 58, 300], repeatRows=1)
        nfr_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F8FAFC")],
                    ),
                ]
            )
        )
        story.append(nfr_table)
    else:
        story.append(Paragraph("<i>No non-functional requirements extracted.</i>", body_style))

    # Business Rules
    if analysis.requirements.business_rules:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Business Rules", h2_style))
        for br in analysis.requirements.business_rules:
            story.append(Paragraph(f"• &nbsp; {safe_text(br)}", bullet_style))

    # Constraints
    if analysis.requirements.constraints:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Constraints", h2_style))
        for c in analysis.requirements.constraints:
            story.append(Paragraph(f"• &nbsp; {safe_text(c)}", bullet_style))

    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # 3. Ambiguity & Validation Analysis
    # ---------------------------------------------------------
    story.append(Paragraph("3. Ambiguity &amp; Validation Analysis", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=6))

    if analysis.validation.validation_summary:
        story.append(
            Paragraph(
                f"<b>Validation Summary:</b> {safe_text(analysis.validation.validation_summary)}",
                body_style,
            )
        )

    if analysis.validation.ambiguities:
        story.append(Paragraph("Identified Ambiguities &amp; Suggested Clarifications", h2_style))
        for idx, amb in enumerate(analysis.validation.ambiguities, start=1):
            amb_content = [
                Paragraph(
                    f"<b>{idx}. Ref: {safe_text(amb.requirement_reference)}</b> "
                    f"&nbsp;[{safe_text(amb.severity)} Severity]",
                    table_cell_bold,
                ),
                Paragraph(f"<b>Problem:</b> {safe_text(amb.problem)}", body_style),
                Paragraph(f"<b>Why Problematic:</b> {safe_text(amb.why_problematic)}", body_style),
                Paragraph(
                    f"<b>Suggested Clarification:</b> {safe_text(amb.suggested_clarification)}",
                    callout_style,
                ),
            ]
            amb_table = Table([[amb_content]], colWidths=[523])
            amb_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(KeepTogether([amb_table, Spacer(1, 6)]))

    if analysis.validation.missing_information:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Missing Information / Gaps", h2_style))
        for item in analysis.validation.missing_information:
            story.append(Paragraph(f"• &nbsp; [Gap] {safe_text(item)}", bullet_style))

    if analysis.validation.conflicts_detected:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Conflicting Requirements Detected", h2_style))
        for item in analysis.validation.conflicts_detected:
            story.append(Paragraph(f"• &nbsp; [Conflict] {safe_text(item)}", bullet_style))

    if analysis.validation.deterministic_issues:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Automated Tool Findings (Deterministic Validator)", h2_style))
        for item in analysis.validation.deterministic_issues:
            story.append(Paragraph(f"• &nbsp; [Warning] {safe_text(item)}", bullet_style))

    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # 4. Agile User Stories & Acceptance Criteria
    # ---------------------------------------------------------
    story.append(Paragraph("4. Agile User Stories &amp; Acceptance Criteria", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=6))

    if analysis.user_stories.summary:
        story.append(Paragraph(safe_text(analysis.user_stories.summary), body_style))

    if analysis.user_stories.stories:
        for story_item in analysis.user_stories.stories:
            story_elements: List[Any] = []
            story_elements.append(
                Paragraph(
                    f"<b>Story {safe_text(story_item.id)}: {safe_text(story_item.role)}</b> "
                    f"&nbsp;({safe_text(story_item.priority)} Priority)",
                    h2_style,
                )
            )

            # Story statement in callout block
            story_quote = [Paragraph(f"<b>{safe_text(story_item.user_story_text)}</b>", callout_style)]
            quote_table = Table([[story_quote]], colWidths=[523])
            quote_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFDBFE")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story_elements.append(quote_table)
            story_elements.append(Spacer(1, 4))

            # Acceptance Criteria
            if story_item.acceptance_criteria:
                story_elements.append(
                    Paragraph("<b>Acceptance Criteria (Given / When / Then):</b>", body_style)
                )
                for ac in story_item.acceptance_criteria:
                    ac_text = (
                        f"• &nbsp; <b>{safe_text(ac.id)} — {safe_text(ac.scenario)}</b><br/>"
                        f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Given:</b> {safe_text(ac.given)}<br/>"
                        f"&nbsp;&nbsp;&nbsp;&nbsp;<b>When:</b> {safe_text(ac.when)}<br/>"
                        f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Then:</b> {safe_text(ac.then)}"
                    )
                    story_elements.append(Paragraph(ac_text, bullet_style))

            story_elements.append(Spacer(1, 6))
            story.append(KeepTogether(story_elements))

    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # 5. Software Architecture Proposal
    # ---------------------------------------------------------
    story.append(Paragraph("5. Software Architecture Proposal", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=6))

    if analysis.architecture.architecture_style:
        story.append(
            Paragraph(
                f"<b>Recommended Architecture Style:</b> {safe_text(analysis.architecture.architecture_style)}",
                body_style,
            )
        )

    if analysis.architecture.rationale:
        story.append(
            Paragraph(
                f"<b>Architecture Rationale:</b> {safe_text(analysis.architecture.rationale)}",
                body_style,
            )
        )

    # Architecture Diagram
    if analysis.architecture.text_diagram:
        story.append(Paragraph("Architecture Diagram", h2_style))
        clean_diagram = safe_text(analysis.architecture.text_diagram).strip()
        diag_block = Preformatted(clean_diagram, code_style)
        diag_table = Table([[diag_block]], colWidths=[523])
        diag_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(KeepTogether([diag_table, Spacer(1, 6)]))

    # Main Architecture Components
    if analysis.architecture.components:
        story.append(Paragraph("Main Architecture Components", h2_style))
        comp_data = [
            [
                Paragraph("<b>Component</b>", table_header_style),
                Paragraph("<b>Layer</b>", table_header_style),
                Paragraph("<b>Technology</b>", table_header_style),
                Paragraph("<b>Responsibility</b>", table_header_style),
            ]
        ]
        for comp in analysis.architecture.components:
            comp_data.append(
                [
                    Paragraph(safe_text(comp.name), table_cell_bold),
                    Paragraph(safe_text(comp.layer), table_cell_style),
                    Paragraph(safe_text(comp.technology_recommendation), table_cell_style),
                    Paragraph(safe_text(comp.responsibility), table_cell_style),
                ]
            )

        comp_table = Table(comp_data, colWidths=[115, 80, 110, 218], repeatRows=1)
        comp_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F8FAFC")],
                    ),
                ]
            )
        )
        story.append(comp_table)

    # Database & Storage
    if analysis.architecture.database_recommendations:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Database &amp; Storage Recommendations", h2_style))
        for db in analysis.architecture.database_recommendations:
            story.append(Paragraph(f"• &nbsp; {safe_text(db)}", bullet_style))

    # Authentication & Security
    if analysis.architecture.authentication_strategy:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Authentication &amp; Security Strategy", h2_style))
        story.append(Paragraph(safe_text(analysis.architecture.authentication_strategy), body_style))

    # External Integrations
    if analysis.architecture.external_services:
        story.append(Spacer(1, 4))
        story.append(Paragraph("External Integrations &amp; Services", h2_style))
        for s in analysis.architecture.external_services:
            story.append(Paragraph(f"• &nbsp; {safe_text(s)}", bullet_style))

    # Component Communication Flow
    if analysis.architecture.communication_flow:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Component Communication Flow", h2_style))
        for flow in analysis.architecture.communication_flow:
            story.append(Paragraph(f"• &nbsp; {safe_text(flow)}", bullet_style))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=6))
    story.append(
        Paragraph(
            "<i>Report generated automatically by Intelligent Software Requirement Analyst (PS-2 Multi-Agent System)</i>",
            body_style,
        )
    )

    # Build PDF with dynamic NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
