"""
Result Writer Tool for Intelligent Software Requirement Analyst.
Persists structured analysis artifacts into JSON and readable Markdown formats.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from app.models.schemas import FinalAnalysisResult
from app.config import OUTPUT_DIR

logger = logging.getLogger("RequirementAnalyst.ResultWriter")


def generate_markdown_report(analysis: FinalAnalysisResult) -> str:
    """Generate a clean, professional Markdown report from FinalAnalysisResult."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lines = []
    lines.append("# Intelligent Software Requirement Analysis Report")
    lines.append(f"**Generated On:** {timestamp}  ")
    lines.append(f"**Document Source:** {analysis.document_source}  ")
    lines.append(f"**Quality Score:** {analysis.validation.overall_quality_score}/10  ")
    lines.append(f"**System Status:** {analysis.status.upper()}  \n")
    lines.append("---")
    
    # Section 1: Executive Summary & Goals
    lines.append("## 1. Executive Summary & System Objectives")
    if analysis.requirements.summary:
        lines.append(f"{analysis.requirements.summary}\n")
    
    if analysis.requirements.system_goals:
        lines.append("### Key System Goals")
        for goal in analysis.requirements.system_goals:
            lines.append(f"- {goal}")
        lines.append("")

    if analysis.requirements.target_actors:
        lines.append("### Target Actors / Personas")
        for actor in analysis.requirements.target_actors:
            lines.append(f"- **{actor}**")
        lines.append("")

    # Section 2: Extracted Requirements
    lines.append("## 2. Extracted Requirements")
    lines.append("### Functional Requirements (FR)")
    if analysis.requirements.functional_requirements:
        lines.append("| ID | Title | Priority | Description |")
        lines.append("|---|---|---|---|")
        for req in analysis.requirements.functional_requirements:
            clean_desc = req.description.replace("\n", " ").replace("|", "\\|")
            lines.append(f"| {req.id} | {req.title} | {req.priority} | {clean_desc} |")
        lines.append("")
    else:
        lines.append("_No functional requirements extracted._\n")

    lines.append("### Non-Functional Requirements (NFR)")
    if analysis.requirements.non_functional_requirements:
        lines.append("| ID | Title | Priority | Description |")
        lines.append("|---|---|---|---|")
        for req in analysis.requirements.non_functional_requirements:
            clean_desc = req.description.replace("\n", " ").replace("|", "\\|")
            lines.append(f"| {req.id} | {req.title} | {req.priority} | {clean_desc} |")
        lines.append("")
    else:
        lines.append("_No non-functional requirements extracted._\n")

    if analysis.requirements.business_rules:
        lines.append("### Business Rules")
        for br in analysis.requirements.business_rules:
            lines.append(f"- {br}")
        lines.append("")

    if analysis.requirements.constraints:
        lines.append("### Constraints")
        for c in analysis.requirements.constraints:
            lines.append(f"- {c}")
        lines.append("")

    # Section 3: Ambiguity & Validation Analysis
    lines.append("## 3. Ambiguity & Validation Analysis")
    lines.append(f"**Validation Summary:** {analysis.validation.validation_summary}\n")

    if analysis.validation.ambiguities:
        lines.append("### Identified Ambiguities & Suggested Clarifications")
        for idx, amb in enumerate(analysis.validation.ambiguities, start=1):
            lines.append(f"#### {idx}. Ref: `{amb.requirement_reference}` [{amb.severity} Priority]")
            lines.append(f"- **Problem:** {amb.problem}")
            lines.append(f"- **Why Problematic:** {amb.why_problematic}")
            lines.append(f"- **Suggested Clarification:** {amb.suggested_clarification}\n")

    if analysis.validation.missing_information:
        lines.append("### Missing Information / Gaps")
        for item in analysis.validation.missing_information:
            lines.append(f"- ⚠️ {item}")
        lines.append("")

    if analysis.validation.conflicts_detected:
        lines.append("### Conflicting Requirements Detected")
        for item in analysis.validation.conflicts_detected:
            lines.append(f"- ⚡ {item}")
        lines.append("")

    if analysis.validation.deterministic_issues:
        lines.append("### Automated Heuristic & Metric Warnings")
        for item in analysis.validation.deterministic_issues:
            lines.append(f"- 🔍 {item}")
        lines.append("")

    # Section 4: Agile User Stories & Acceptance Criteria
    lines.append("## 4. Agile User Stories & Acceptance Criteria")
    lines.append(f"{analysis.user_stories.summary}\n")

    for story in analysis.user_stories.stories:
        lines.append(f"### Story `{story.id}`: {story.role} ({story.priority} Priority)")
        lines.append(f"> **{story.user_story_text}**\n")
        
        if story.acceptance_criteria:
            lines.append("**Acceptance Criteria (Given / When / Then):**\n")
            for ac in story.acceptance_criteria:
                lines.append(f"- **{ac.id} - {ac.scenario}**")
                lines.append(f"  - **Given** {ac.given}")
                lines.append(f"  - **When** {ac.when}")
                lines.append(f"  - **Then** {ac.then}\n")

    # Section 5: Architecture Proposal
    lines.append("## 5. Software Architecture Proposal")
    lines.append(f"**Recommended Style:** {analysis.architecture.architecture_style}\n")
    lines.append(f"**Rationale:** {analysis.architecture.rationale}\n")

    lines.append("### Architecture Diagram")
    lines.append("```text")
    lines.append(analysis.architecture.text_diagram)
    lines.append("```\n")

    lines.append("### Main Architecture Components")
    lines.append("| Component | Layer | Recommended Tech | Responsibility |")
    lines.append("|---|---|---|---|")
    for comp in analysis.architecture.components:
        lines.append(f"| {comp.name} | {comp.layer} | {comp.technology_recommendation} | {comp.responsibility} |")
    lines.append("")

    if analysis.architecture.database_recommendations:
        lines.append("### Database & Storage Recommendations")
        for db in analysis.architecture.database_recommendations:
            lines.append(f"- {db}")
        lines.append("")

    if analysis.architecture.authentication_strategy:
        lines.append(f"### Authentication & Security Strategy\n{analysis.architecture.authentication_strategy}\n")

    if analysis.architecture.external_services:
        lines.append("### External Integrations & Services")
        for s in analysis.architecture.external_services:
            lines.append(f"- {s}")
        lines.append("")

    if analysis.architecture.communication_flow:
        lines.append("### Component Communication Flow")
        for flow in analysis.architecture.communication_flow:
            lines.append(f"- {flow}")
        lines.append("")

    lines.append("---")
    lines.append("*Report generated automatically by Intelligent Software Requirement Analyst (PS-2 Multi-Agent System)*")
    return "\n".join(lines)


def save_analysis_results(analysis: FinalAnalysisResult, output_dir: str = OUTPUT_DIR) -> Tuple[str, str]:
    """
    Save the final analysis as both JSON and Markdown files in output_dir.
    Uses stable filenames latest_analysis.json and latest_analysis.md,
    overwriting previous results on each run.
    Returns (json_path, markdown_path).
    """
    os.makedirs(output_dir, exist_ok=True)
    
    json_filename = "latest_analysis.json"
    md_filename = "latest_analysis.md"
    
    json_path = os.path.join(output_dir, json_filename)
    md_path = os.path.join(output_dir, md_filename)

    logger.info("Persisting analysis to JSON: %s", json_path)
    with open(json_path, "w", encoding="utf-8") as f:
        # Convert Pydantic model to clean dictionary
        json.dump(analysis.model_dump(), f, indent=2, ensure_ascii=False)

    logger.info("Persisting analysis to Markdown: %s", md_path)
    markdown_content = generate_markdown_report(analysis)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return json_path, md_path
