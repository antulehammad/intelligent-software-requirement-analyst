"""
Agent 1: Requirement Extraction Agent
Extracts structured software requirements from natural language documentation.
Identifies functional, non-functional requirements, actors, goals, business rules,
constraints, and domain entities.
"""

import logging
from typing import Any
from app.models.schemas import ExtractedRequirements
from app.agents.llm_util import call_gemini_json

logger = logging.getLogger("RequirementAnalyst.RequirementAgent")

REQUIREMENT_EXTRACTION_SYSTEM_PROMPT = """
You are an expert Software Requirements Engineer and Systems Analyst (ISO/IEC/IEEE 29148).
Your mission is to rigorously analyze the input natural language requirements document and extract:
1. System Goals (high-level objectives)
2. Target Actors (user roles, external systems, personas)
3. Functional Requirements (specific capabilities, features, behaviors with ID e.g. FR-01)
4. Non-Functional Requirements (performance, security, scalability, usability, availability with ID e.g. NFR-01)
5. Business Rules (policies, calculations, compliance guidelines)
6. Constraints (technology limits, regulatory compliance, platform limitations)
7. Entities / Key Data Elements (domain models like User, Order, Payment)
8. Summary (concise executive overview)

Ensure all extracted items are categorized accurately.
Return your analysis strictly in valid JSON matching this schema:
{
  "system_goals": ["goal 1", "goal 2"],
  "target_actors": ["Customer", "Admin"],
  "functional_requirements": [
    {
      "id": "FR-01",
      "category": "Functional",
      "title": "Short title",
      "description": "Clear description of behavior",
      "priority": "High"
    }
  ],
  "non_functional_requirements": [
    {
      "id": "NFR-01",
      "category": "Non-Functional",
      "title": "Short title",
      "description": "Quality attribute description",
      "priority": "Medium"
    }
  ],
  "business_rules": ["rule 1"],
  "constraints": ["constraint 1"],
  "entities_data": ["User", "Order"],
  "summary": "Executive summary paragraph"
}
"""


def extract_requirements(document_text: str, client: Any, model: str) -> ExtractedRequirements:
    """
    Execute Agent 1: Extract requirements from document text using Gemini.
    """
    logger.info("Agent 1 [Requirement Extraction] started. Document length: %d chars", len(document_text))
    
    prompt = f"""
Please analyze the following software requirements document and extract all requirements, actors, goals, rules, constraints, and entities:

--- DOCUMENT START ---
{document_text}
--- DOCUMENT END ---
"""

    data = call_gemini_json(
        client=client,
        model=model,
        prompt=prompt,
        system_instruction=REQUIREMENT_EXTRACTION_SYSTEM_PROMPT,
    )

    # Validate and structure with Pydantic
    requirements = ExtractedRequirements.model_validate(data)
    logger.info(
        "Agent 1 finished successfully: %d FRs, %d NFRs, %d actors identified.",
        len(requirements.functional_requirements),
        len(requirements.non_functional_requirements),
        len(requirements.target_actors),
    )
    return requirements
