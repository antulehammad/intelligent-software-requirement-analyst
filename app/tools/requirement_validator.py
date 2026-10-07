"""
Requirement Validation Tool for Intelligent Software Requirement Analyst.
Performs deterministic, rule-based heuristic checks on extracted requirements.
Identifies empty fields, missing actors, vague buzzwords, and quality metrics.
"""

import re
import logging
from typing import Dict, Any, List
from app.models.schemas import ExtractedRequirements

logger = logging.getLogger("RequirementAnalyst.ValidatorTool")

# Common ambiguous / vague terms in requirements engineering (IEEE 830 / ISO 29148)
VAGUE_BUZZWORDS = [
    "fast",
    "quick",
    "as soon as possible",
    "user-friendly",
    "easy to use",
    "scalable",
    "secure",
    "robust",
    "high performance",
    "efficient",
    "real-time",
    "seamless",
    "flexible",
    "intuitive",
    "reliable",
    "best in class",
    "sufficient",
    "modern",
]


def run_deterministic_checks(requirements: ExtractedRequirements) -> Dict[str, Any]:
    """
    Execute deterministic validation rules on extracted requirements.
    
    Checks:
    1. Empty / missing structural fields (goals, actors, functional requirements)
    2. Vague terminology used without quantitative criteria (e.g. 'fast' without ms threshold)
    3. Missing constraints or non-functional requirements
    4. Short or incomplete descriptions (< 15 characters)
    5. Calculates heuristic readiness/quality score
    """
    logger.info("Executing deterministic validation checks...")
    issues: List[str] = []
    warnings: List[str] = []
    vague_keyword_hits: List[Dict[str, str]] = []

    # 1. Structural Checks
    if not requirements.system_goals:
        issues.append("Missing System Goals: The document did not specify any high-level business goals.")
    
    if not requirements.target_actors:
        issues.append("Missing Target Actors: No user roles or system actors were identified.")

    if not requirements.functional_requirements:
        issues.append("Zero Functional Requirements: No core functional specifications were extracted.")
    elif len(requirements.functional_requirements) < 3:
        warnings.append(
            f"Low Functional Requirement Count: Only {len(requirements.functional_requirements)} requirements extracted."
        )

    if not requirements.non_functional_requirements:
        warnings.append("Missing Non-Functional Requirements: No performance, security, or reliability criteria specified.")

    if not requirements.constraints:
        warnings.append("Missing Constraints: No technical, compliance, or timeline constraints defined.")

    # 2. Vague Buzzwords Analysis
    all_req_items = requirements.functional_requirements + requirements.non_functional_requirements
    for req in all_req_items:
        text_to_check = f"{req.title} {req.description}".lower()
        
        # Check description length
        if len(req.description.strip()) < 15:
            issues.append(f"Incomplete Requirement [{req.id}]: Description is too short or lacking context.")

        for word in VAGUE_BUZZWORDS:
            # Pattern match whole word
            pattern = r"\b" + re.escape(word) + r"\b"
            if re.search(pattern, text_to_check):
                vague_keyword_hits.append({
                    "requirement_id": req.id,
                    "keyword": word,
                    "context": req.title
                })
                warnings.append(
                    f"Vague Metric [{req.id} - '{req.title}']: Uses unquantified term '{word}' without measurable SLA/benchmark."
                )

    # 3. Quality Score Calculation (Deterministic 0 - 10)
    score = 10.0
    score -= len(issues) * 1.5
    score -= len(warnings) * 0.3
    score = max(1.0, min(10.0, round(score, 1)))

    logger.info(
        "Deterministic check completed: %d issues, %d warnings, score=%.1f/10",
        len(issues), len(warnings), score
    )

    return {
        "status": "passed" if not issues else "issues_found",
        "quality_score": score,
        "critical_issues": issues,
        "warnings": warnings,
        "vague_keyword_hits": vague_keyword_hits,
        "total_functional_count": len(requirements.functional_requirements),
        "total_nfr_count": len(requirements.non_functional_requirements),
        "total_actors_count": len(requirements.target_actors),
    }
