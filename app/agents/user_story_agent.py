"""
Agent 3: User Story & Acceptance Criteria Agent
Converts validated software requirements into structured Agile User Stories
with Given/When/Then Acceptance Criteria (BDD format).
"""

import logging
from typing import Any
from app.models.schemas import ExtractedRequirements, ValidationResult, UserStoriesResult
from app.agents.llm_util import call_gemini_json

logger = logging.getLogger("RequirementAnalyst.UserStoryAgent")

USER_STORY_SYSTEM_PROMPT = """
You are an Agile Product Owner and Business Analyst expert.
Your job is to translate validated software requirements into high-quality Agile User Stories.

Rules:
1. Every user story must follow the canonical template:
   "As a <type of user>, I want <goal>, so that <benefit>."
2. The role must represent an actual actor/persona identified in the requirements.
3. For EVERY user story, generate 2 to 4 clear Acceptance Criteria in Given/When/Then format:
   - Scenario: Descriptive scenario title
   - Given: Initial preconditions
   - When: Action performed by user/system
   - Then: Measurable expected outcome
4. Assign an ID (e.g. US-01, US-02) and Priority (High, Medium, Low).
5. Cover all primary functional requirements extracted from the document.

Return your analysis strictly in valid JSON matching this schema:
{
  "stories": [
    {
      "id": "US-01",
      "role": "Registered Customer",
      "goal": "filter restaurants by cuisine and rating",
      "benefit": "I can quickly find the food I want to order",
      "user_story_text": "As a Registered Customer, I want to filter restaurants by cuisine and rating, so that I can quickly find the food I want to order.",
      "priority": "High",
      "acceptance_criteria": [
        {
          "id": "AC-01",
          "scenario": "Successful cuisine filtering",
          "given": "The customer is on the restaurant listing page",
          "when": "The customer selects 'Italian' cuisine filter",
          "then": "Only restaurants serving Italian cuisine are displayed in the results within 1 second"
        }
      ]
    }
  ],
  "summary": "Overview of user story breakdown across sprints and epics"
}
"""


def generate_user_stories(
    requirements: ExtractedRequirements,
    validation: ValidationResult,
    client: Any,
    model: str
) -> UserStoriesResult:
    """
    Execute Agent 3: Generate agile user stories and acceptance criteria from requirements.
    """
    logger.info("Agent 3 [User Story & Acceptance Criteria] started.")

    requirements_summary = requirements.model_dump_json(indent=2)
    clarifications = [
        f"{amb.requirement_reference}: {amb.suggested_clarification}"
        for amb in validation.ambiguities[:5]
    ]

    prompt = f"""
Convert the following software requirements into comprehensive agile user stories with BDD acceptance criteria.

REQUIREMENTS:
{requirements_summary}

VALIDATION CLARIFICATIONS TO KEEP IN MIND:
{clarifications}
"""

    data = call_gemini_json(
        client=client,
        model=model,
        prompt=prompt,
        system_instruction=USER_STORY_SYSTEM_PROMPT,
    )

    user_stories = UserStoriesResult.model_validate(data)
    logger.info(
        "Agent 3 finished successfully: Generated %d user stories.",
        len(user_stories.stories),
    )
    return user_stories
