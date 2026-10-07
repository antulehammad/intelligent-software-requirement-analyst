"""
Agent 4: Architecture Proposal Agent
Generates a practical, clean, basic software architecture proposal based on analyzed requirements.
Recommends architecture style, main layers/components, database, authentication,
integrations, communication flow, and a clean text-based architecture diagram.
"""

import logging
from typing import Any
from app.models.schemas import ExtractedRequirements, UserStoriesResult, ArchitectureProposal
from app.agents.llm_util import call_gemini_json

logger = logging.getLogger("RequirementAnalyst.ArchitectureAgent")

ARCHITECTURE_SYSTEM_PROMPT = """
You are a Principal Software Architect.
Your task is to design a clean, pragmatic, and grounded software architecture proposal based on the analyzed requirements and user stories.

Guidelines:
1. Do NOT over-engineer. Avoid complex distributed microservices or Kubernetes unless the requirements explicitly demand hyper-scale.
2. Recommend a solid, proven architecture style (e.g., 3-Tier Layered Architecture, Modular Monolith with REST API, or Client-Server).
3. Specify components for:
   - Frontend (e.g. Web SPA, Mobile App, Streamlit/React)
   - API / Gateway Layer (e.g. FastAPI / Express REST API)
   - Backend Business Logic (Services, Controllers)
   - Database / Persistence (e.g. PostgreSQL, SQLite)
   - Authentication (e.g. JWT, OAuth2)
   - External Services (e.g. Stripe, Twilio, Google Maps if relevant)
4. Outline communication flow clearly.
5. Provide a short explanation of WHY this architecture fits the requirements.
6. Provide a clear ASCII / text-based architecture diagram illustrating data and control flow, customized to this specific system.
   Example format:
   [ End Users / Clients ]
             │
             ▼ (HTTPS / REST)
   [ Frontend Web / Mobile App ]
             │
             ▼ (JSON API)
   [ Backend API Gateway & Controllers ]
             │
             ▼
   [ Business Logic & Domain Services ]
        │                 │
        ▼                 ▼
   [ Database ]     [ External APIs ]

Return your analysis strictly in valid JSON matching this schema:
{
  "architecture_style": "3-Tier Layered Client-Server Architecture",
  "components": [
    {
      "name": "Web & Mobile Client",
      "layer": "Frontend",
      "technology_recommendation": "React / Streamlit / Flutter",
      "responsibility": "Renders UI, handles client state, and interacts with REST API"
    },
    {
      "name": "Application API Server",
      "layer": "API / Backend",
      "technology_recommendation": "Python FastAPI",
      "responsibility": "Routing, authentication verification, business logic orchestration"
    },
    {
      "name": "Relational Database",
      "layer": "Database",
      "technology_recommendation": "PostgreSQL",
      "responsibility": "ACID transactional storage for users, orders, and catalogs"
    }
  ],
  "database_recommendations": [
    "PostgreSQL for structured relational data with foreign key constraints"
  ],
  "authentication_strategy": "JWT (JSON Web Tokens) with Argon2/bcrypt password hashing",
  "external_services": [
    "Payment Gateway (Stripe/PayPal)",
    "Notification Service (SMS/Email via Twilio/SendGrid)"
  ],
  "communication_flow": [
    "1. Client sends HTTPS requests with Bearer JWT to FastAPI API Gateway.",
    "2. API Gateway validates tokens and invokes appropriate domain service.",
    "3. Domain service interacts with PostgreSQL via ORM and commits transactions."
  ],
  "rationale": "A 3-tier modular architecture provides the optimal balance of simplicity, maintainability, and rapid development without distributed system overhead.",
  "text_diagram": "[ User ]\\n   ↓\\n[ Frontend ]\\n   ↓\\n[ API / Backend ]\\n   ↓\\n[ Database ]"
}
"""


def propose_architecture(
    requirements: ExtractedRequirements,
    user_stories: UserStoriesResult,
    client: Any,
    model: str
) -> ArchitectureProposal:
    """
    Execute Agent 4: Generate architecture proposal based on extracted requirements and stories.
    """
    logger.info("Agent 4 [Architecture Proposal] started.")

    req_summary = {
        "goals": requirements.system_goals,
        "actors": requirements.target_actors,
        "nfrs": [n.title + ": " + n.description for n in requirements.non_functional_requirements],
        "constraints": requirements.constraints,
        "story_count": len(user_stories.stories),
    }

    prompt = f"""
Design a pragmatic, basic software architecture for the following system:

SYSTEM SPECIFICATIONS:
{req_summary}
"""

    data = call_gemini_json(
        client=client,
        model=model,
        prompt=prompt,
        system_instruction=ARCHITECTURE_SYSTEM_PROMPT,
    )

    architecture = ArchitectureProposal.model_validate(data)
    logger.info(
        "Agent 4 finished successfully: Style '%s', %d components proposed.",
        architecture.architecture_style,
        len(architecture.components),
    )
    return architecture
