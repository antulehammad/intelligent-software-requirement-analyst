"""
Pydantic Schemas for Intelligent Software Requirement Analyst.
Defines structured data contracts for all 4 agents, tools, API, and storage.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Agent 1: Requirement Extraction Models
# ---------------------------------------------------------

class RequirementItem(BaseModel):
    """Individual software requirement."""
    id: str = Field(..., description="Unique identifier like FR-01, NFR-01, BR-01")
    category: str = Field(..., description="Category: Functional, Non-Functional, Business Rule, Constraint")
    title: str = Field(..., description="Short descriptive title of the requirement")
    description: str = Field(..., description="Detailed explanation of the requirement")
    priority: str = Field(default="Medium", description="Priority level: High, Medium, Low")


class ExtractedRequirements(BaseModel):
    """Complete structured output from Agent 1 (Requirement Extraction)."""
    system_goals: List[str] = Field(default_factory=list, description="High-level objectives of the system")
    target_actors: List[str] = Field(default_factory=list, description="Identified user personas or actors")
    functional_requirements: List[RequirementItem] = Field(default_factory=list, description="Functional requirements")
    non_functional_requirements: List[RequirementItem] = Field(default_factory=list, description="Quality attributes, security, performance, etc.")
    business_rules: List[str] = Field(default_factory=list, description="Core business logic and domain policies")
    constraints: List[str] = Field(default_factory=list, description="Technical, regulatory, or business constraints")
    entities_data: List[str] = Field(default_factory=list, description="Key domain entities and data attributes")
    summary: str = Field(default="", description="Executive summary of the software requirements")


# ---------------------------------------------------------
# Agent 2: Ambiguity & Validation Models
# ---------------------------------------------------------

class AmbiguityItem(BaseModel):
    """Identified ambiguity, vague statement, or missing specification."""
    requirement_reference: str = Field(..., description="Requirement ID or natural statement reference")
    problem: str = Field(..., description="Nature of the problem (e.g. Unmeasured metric, Vague actor)")
    why_problematic: str = Field(..., description="Why this statement causes misinterpretation or risk")
    suggested_clarification: str = Field(..., description="Concrete clarification question or suggested rewrite")
    severity: str = Field(default="Medium", description="Impact severity: High, Medium, Low")


class ValidationResult(BaseModel):
    """Complete output from Agent 2 (Ambiguity & Validation)."""
    ambiguities: List[AmbiguityItem] = Field(default_factory=list, description="List of detected ambiguities")
    missing_information: List[str] = Field(default_factory=list, description="Important omitted details or missing flows")
    conflicts_detected: List[str] = Field(default_factory=list, description="Contradictions between different requirements")
    deterministic_issues: List[str] = Field(default_factory=list, description="Heuristic issues flagged by the validation tool")
    overall_quality_score: float = Field(default=7.0, description="Overall requirement quality score out of 10")
    validation_summary: str = Field(default="", description="High-level synthesis of requirements readiness")


# ---------------------------------------------------------
# Agent 3: User Stories & Acceptance Criteria Models
# ---------------------------------------------------------

class AcceptanceCriterion(BaseModel):
    """BDD-style acceptance criterion for a user story."""
    id: str = Field(..., description="Acceptance criterion ID e.g. AC-01")
    scenario: str = Field(..., description="Scenario title e.g. Successful checkout")
    given: str = Field(..., description="Given initial context / preconditions")
    when: str = Field(..., description="When user performs an action")
    then: str = Field(..., description="Then expected outcome / system response")


class UserStoryItem(BaseModel):
    """User story following standard agile template."""
    id: str = Field(..., description="User story identifier e.g. US-01")
    role: str = Field(..., description="Target actor (As a <type of user>)")
    goal: str = Field(..., description="User goal (I want <goal>)")
    benefit: str = Field(..., description="Business or personal benefit (so that <benefit>)")
    user_story_text: str = Field(..., description="Formatted string: As a <role>, I want <goal>, so that <benefit>.")
    acceptance_criteria: List[AcceptanceCriterion] = Field(default_factory=list, description="Acceptance criteria for this story")
    priority: str = Field(default="Medium", description="Sprint priority: High, Medium, Low")


class UserStoriesResult(BaseModel):
    """Complete output from Agent 3 (User Stories & Acceptance Criteria)."""
    stories: List[UserStoryItem] = Field(default_factory=list, description="Generated agile user stories")
    summary: str = Field(default="", description="Overview of the user story breakdown")


# ---------------------------------------------------------
# Agent 4: Architecture Proposal Models
# ---------------------------------------------------------

class ArchitectureComponent(BaseModel):
    """Individual component in proposed system architecture."""
    name: str = Field(..., description="Component name e.g. Client Web App, Order Service")
    layer: str = Field(..., description="Layer: Frontend, API / Gateway, Backend Logic, Database, Auth, External")
    technology_recommendation: str = Field(..., description="Suggested tech stack e.g. Streamlit, FastAPI, PostgreSQL, Redis")
    responsibility: str = Field(..., description="Primary responsibility of this component")


class ArchitectureProposal(BaseModel):
    """Complete output from Agent 4 (Architecture Proposal)."""
    architecture_style: str = Field(..., description="Recommended style e.g. 3-Tier Layered Architecture / Modular Monolith")
    components: List[ArchitectureComponent] = Field(default_factory=list, description="Key architecture components")
    database_recommendations: List[str] = Field(default_factory=list, description="Data storage solutions and schema advice")
    authentication_strategy: str = Field(default="", description="Recommended authentication & authorization approach")
    external_services: List[str] = Field(default_factory=list, description="External APIs e.g. Payment Gateway, Maps, SMS")
    communication_flow: List[str] = Field(default_factory=list, description="Flow of interactions between components")
    rationale: str = Field(default="", description="Justification for why this architecture suits the requirements")
    text_diagram: str = Field(default="", description="ASCII / text-based architecture block diagram")


# ---------------------------------------------------------
# Final Aggregate Result & API Payloads
# ---------------------------------------------------------

class FinalAnalysisResult(BaseModel):
    """Aggregated result holding all artifacts from the 4-agent workflow."""
    document_source: str = Field(default="Direct Input", description="Name of source document or direct input label")
    requirements: ExtractedRequirements
    validation: ValidationResult
    user_stories: UserStoriesResult
    architecture: ArchitectureProposal
    json_path: Optional[str] = Field(default=None, description="Local path to generated JSON result")
    markdown_path: Optional[str] = Field(default=None, description="Local path to generated Markdown report")
    status: str = Field(default="completed", description="Execution status")
    errors: List[str] = Field(default_factory=list, description="Any non-fatal errors or warnings encountered")
    fallback_used: bool = Field(default=False, description="Whether fallback model was activated")
    fallback_message: Optional[str] = Field(default=None, description="Status notice if fallback model was activated")



class TextAnalysisRequest(BaseModel):
    """Payload for text-based analysis API."""
    text: str = Field(..., min_length=10, description="Natural language software requirements text")
    document_name: Optional[str] = Field(default="Direct Input", description="Optional label for the document")
    gemini_api_key: Optional[str] = Field(default=None, description="Optional custom Gemini API key")
    gemini_model: Optional[str] = Field(default=None, description="Optional custom Gemini model name")



class AnalysisApiResponse(BaseModel):
    """Standard API response schema for FastAPI endpoints."""
    success: bool
    message: str
    data: Optional[FinalAnalysisResult] = None
    errors: List[str] = Field(default_factory=list)
