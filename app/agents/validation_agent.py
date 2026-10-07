"""
Agent 2: Ambiguity & Validation Agent
Reviews extracted requirements to identify ambiguities, missing information,
conflicting specifications, vague metrics, and unclear actors/inputs/outputs.
Actively calls the Requirement Validation Tool for deterministic checks.
"""

import json
import logging
from typing import Any
from app.models.schemas import ExtractedRequirements, ValidationResult
from app.tools.requirement_validator import run_deterministic_checks
from app.agents.llm_util import call_gemini_json

logger = logging.getLogger("RequirementAnalyst.ValidationAgent")

VALIDATION_SYSTEM_PROMPT = """
You are a Senior Software Quality Assurance & Requirements Validation Auditor.
Your job is to critically review extracted software requirements and detect:
1. Ambiguous requirements (phrases open to multiple interpretations)
2. Missing information (unspecified edge cases, timeouts, currency, error handling)
3. Conflicting requirements (contradictions between two or more requirements/rules)
4. Vague statements (buzzwords like "fast", "user-friendly", "scalable" without quantifiable metrics)
5. Unclear actors (who initiates or receives an action)
6. Unclear inputs/outputs (unspecified data formats, payloads, responses)
7. Missing constraints (unspecified system boundaries, rate limits, storage policies)

For EACH identified issue, you must supply:
- requirement_reference: The ID or title of the requirement/statement
- problem: Clear summary of the flaw
- why_problematic: How this ambiguity causes development, cost, or testing risks
- suggested_clarification: Actionable recommendation or question to ask stakeholders
- severity: "High", "Medium", or "Low"

You will also be given findings from an automated deterministic validation tool.
Incorporate those findings and provide a comprehensive validation summary and quality score (0.0 to 10.0).

Return your analysis strictly in valid JSON matching this schema:
{
  "ambiguities": [
    {
      "requirement_reference": "FR-01",
      "problem": "Unspecified payment provider",
      "why_problematic": "Developers will not know which SDK to integrate or fees applicable",
      "suggested_clarification": "Specify whether Stripe, PayPal, or UPI should be integrated",
      "severity": "High"
    }
  ],
  "missing_information": [
    "Password reset flow lacks token expiry duration"
  ],
  "conflicts_detected": [
    "Conflict between instant cancellation and restaurant 5-minute prep rule"
  ],
  "validation_summary": "Summary of requirements readiness for development",
  "overall_quality_score": 6.5
}
"""


def validate_requirements(requirements: ExtractedRequirements, client: Any, model: str) -> ValidationResult:
    """
    Execute Agent 2: Run deterministic validation tool, then prompt Gemini to evaluate
    ambiguities, conflicts, gaps, and suggested clarifications.
    """
    logger.info("Agent 2 [Ambiguity & Validation] started.")

    # 1. TOOL CALL: Run deterministic checks tool
    logger.info("Agent 2 invoking Requirement Validation Tool...")
    tool_results = run_deterministic_checks(requirements)
    logger.info("Tool check findings: score=%.1f, warnings=%d", tool_results["quality_score"], len(tool_results["warnings"]))

    # 2. Prepare context for LLM validation
    requirements_json = requirements.model_dump_json(indent=2)
    tool_findings_json = json.dumps(tool_results, indent=2)

    prompt = f"""
Please critically audit and validate the following software requirements.

AUTOMATED TOOL FINDINGS:
{tool_findings_json}

EXTRACTED REQUIREMENTS:
{requirements_json}
"""

    data = call_gemini_json(
        client=client,
        model=model,
        prompt=prompt,
        system_instruction=VALIDATION_SYSTEM_PROMPT,
    )

    # Combine deterministic tool warnings into the final validation model
    deterministic_issues = tool_results.get("critical_issues", []) + tool_results.get("warnings", [])
    data["deterministic_issues"] = deterministic_issues

    # If model quality score differs or was defaulted, ensure it's in valid range
    score = data.get("overall_quality_score", tool_results["quality_score"])
    try:
        data["overall_quality_score"] = float(score)
    except (ValueError, TypeError):
        data["overall_quality_score"] = tool_results["quality_score"]

    validation_result = ValidationResult.model_validate(data)
    logger.info(
        "Agent 2 finished successfully: %d ambiguities, %d missing items, score=%.1f/10",
        len(validation_result.ambiguities),
        len(validation_result.missing_information),
        validation_result.overall_quality_score,
    )
    return validation_result
