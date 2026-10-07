"""
LangGraph Multi-Agent Orchestration Workflow for Intelligent Software Requirement Analyst.
Connects the 4 specialized agents and deterministic tools in a sequential StateGraph:
START -> Extraction Agent -> Validation Agent -> User Story Agent -> Architecture Agent -> Result Writer Tool -> END
"""

import logging
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, START, END

from app.config import get_gemini_client, GEMINI_MODEL
from app.models.schemas import (
    ExtractedRequirements,
    ValidationResult,
    UserStoriesResult,
    ArchitectureProposal,
    FinalAnalysisResult,
)
from app.agents.requirement_agent import extract_requirements
from app.agents.validation_agent import validate_requirements
from app.agents.user_story_agent import generate_user_stories
from app.agents.architecture_agent import propose_architecture
from app.agents.llm_util import is_fallback_activated, get_fallback_message, reset_fallback_status
from app.tools.result_writer import save_analysis_results

logger = logging.getLogger("RequirementAnalyst.Workflow")


class AnalystState(TypedDict):
    """Shared state object passed through the LangGraph agent workflow."""
    raw_text: str
    document_source: str
    gemini_api_key: Optional[str]
    gemini_model: Optional[str]
    requirements: Optional[Dict[str, Any]]
    validation: Optional[Dict[str, Any]]
    user_stories: Optional[Dict[str, Any]]
    architecture: Optional[Dict[str, Any]]
    json_path: Optional[str]
    markdown_path: Optional[str]
    status: str
    errors: List[str]
    fallback_used: Optional[bool]
    fallback_message: Optional[str]



# ---------------------------------------------------------
# Graph Nodes
# ---------------------------------------------------------

def extraction_node(state: AnalystState) -> Dict[str, Any]:
    """Node 1: Execute Agent 1 (Requirement Extraction)."""
    logger.info("Executing Workflow Node: extraction_node")
    try:
        client = get_gemini_client(state.get("gemini_api_key"))
        model = state.get("gemini_model") or GEMINI_MODEL
        reqs = extract_requirements(state["raw_text"], client, model)
        return {
            "requirements": reqs.model_dump(),
            "status": "extracted",
            "fallback_used": is_fallback_activated() or bool(state.get("fallback_used")),
            "fallback_message": get_fallback_message() or state.get("fallback_message"),
        }
    except Exception as e:
        logger.error("Error in extraction_node: %s", str(e))
        return {
            "errors": state.get("errors", []) + [f"Requirement Extraction Agent Error: {e}"],
            "status": "failed",
        }


def validation_node(state: AnalystState) -> Dict[str, Any]:
    """Node 2: Execute Agent 2 (Ambiguity & Validation) with deterministic tool checks."""
    logger.info("Executing Workflow Node: validation_node")
    if state.get("status") == "failed" or not state.get("requirements"):
        return {"status": "failed"}

    try:
        client = get_gemini_client(state.get("gemini_api_key"))
        model = state.get("gemini_model") or GEMINI_MODEL
        reqs = ExtractedRequirements.model_validate(state["requirements"])
        val_result = validate_requirements(reqs, client, model)
        return {
            "validation": val_result.model_dump(),
            "status": "validated",
            "fallback_used": is_fallback_activated() or bool(state.get("fallback_used")),
            "fallback_message": get_fallback_message() or state.get("fallback_message"),
        }
    except Exception as e:
        logger.error("Error in validation_node: %s", str(e))
        return {
            "errors": state.get("errors", []) + [f"Validation Agent Error: {e}"],
            "status": "failed",
        }


def user_story_node(state: AnalystState) -> Dict[str, Any]:
    """Node 3: Execute Agent 3 (User Story & Acceptance Criteria)."""
    logger.info("Executing Workflow Node: user_story_node")
    if state.get("status") == "failed" or not state.get("requirements") or not state.get("validation"):
        return {"status": "failed"}

    try:
        client = get_gemini_client(state.get("gemini_api_key"))
        model = state.get("gemini_model") or GEMINI_MODEL
        reqs = ExtractedRequirements.model_validate(state["requirements"])
        val_result = ValidationResult.model_validate(state["validation"])
        stories_result = generate_user_stories(reqs, val_result, client, model)
        return {
            "user_stories": stories_result.model_dump(),
            "status": "stories_generated",
            "fallback_used": is_fallback_activated() or bool(state.get("fallback_used")),
            "fallback_message": get_fallback_message() or state.get("fallback_message"),
        }
    except Exception as e:
        logger.error("Error in user_story_node: %s", str(e))
        return {
            "errors": state.get("errors", []) + [f"User Story Agent Error: {e}"],
            "status": "failed",
        }


def architecture_node(state: AnalystState) -> Dict[str, Any]:
    """Node 4: Execute Agent 4 (Architecture Proposal)."""
    logger.info("Executing Workflow Node: architecture_node")
    if state.get("status") == "failed" or not state.get("requirements") or not state.get("user_stories"):
        return {"status": "failed"}

    try:
        client = get_gemini_client(state.get("gemini_api_key"))
        model = state.get("gemini_model") or GEMINI_MODEL
        reqs = ExtractedRequirements.model_validate(state["requirements"])
        stories_result = UserStoriesResult.model_validate(state["user_stories"])
        arch_result = propose_architecture(reqs, stories_result, client, model)
        return {
            "architecture": arch_result.model_dump(),
            "status": "architecture_proposed",
            "fallback_used": is_fallback_activated() or bool(state.get("fallback_used")),
            "fallback_message": get_fallback_message() or state.get("fallback_message"),
        }
    except Exception as e:
        logger.error("Error in architecture_node: %s", str(e))
        return {
            "errors": state.get("errors", []) + [f"Architecture Agent Error: {e}"],
            "status": "failed",
        }


def result_writer_node(state: AnalystState) -> Dict[str, Any]:
    """Node 5: Execute Result Writer Tool to persist JSON & Markdown analysis."""
    logger.info("Executing Workflow Node: result_writer_node (Tool Calling)")
    if state.get("status") == "failed":
        return {"status": "failed"}

    fallback_active = is_fallback_activated() or bool(state.get("fallback_used"))
    fallback_notice = get_fallback_message() or state.get("fallback_message")

    try:
        final_analysis = FinalAnalysisResult(
            document_source=state.get("document_source", "Direct Input"),
            requirements=ExtractedRequirements.model_validate(state["requirements"]),
            validation=ValidationResult.model_validate(state["validation"]),
            user_stories=UserStoriesResult.model_validate(state["user_stories"]),
            architecture=ArchitectureProposal.model_validate(state["architecture"]),
            status="completed",
            errors=state.get("errors", []),
            fallback_used=fallback_active,
            fallback_message=fallback_notice,
        )

        json_path, md_path = save_analysis_results(final_analysis)
        return {
            "json_path": json_path,
            "markdown_path": md_path,
            "status": "completed",
            "fallback_used": fallback_active,
            "fallback_message": fallback_notice,
        }
    except Exception as e:
        logger.error("Error in result_writer_node: %s", str(e))
        return {
            "errors": state.get("errors", []) + [f"Result Writer Tool Error: {e}"],
            "status": "partial_success",
            "fallback_used": fallback_active,
            "fallback_message": fallback_notice,
        }


# ---------------------------------------------------------
# Build LangGraph Workflow
# ---------------------------------------------------------

def build_analyst_graph():
    """Construct and compile the LangGraph multi-agent workflow."""
    workflow = StateGraph(AnalystState)

    # Register Nodes
    workflow.add_node("extraction", extraction_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("user_stories", user_story_node)
    workflow.add_node("architecture", architecture_node)
    workflow.add_node("result_writer", result_writer_node)

    # Define Linear Sequential Edges
    workflow.add_edge(START, "extraction")
    workflow.add_edge("extraction", "validation")
    workflow.add_edge("validation", "user_stories")
    workflow.add_edge("user_stories", "architecture")
    workflow.add_edge("architecture", "result_writer")
    workflow.add_edge("result_writer", END)

    compiled_graph = workflow.compile()
    return compiled_graph


# Pre-compile the graph for efficient reuse
analyst_graph = build_analyst_graph()


def run_analyst_workflow(
    document_text: str,
    source_name: str = "Direct Input",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> FinalAnalysisResult:
    """
    Convenient entry point to execute the complete LangGraph multi-agent workflow.
    Returns FinalAnalysisResult object or raises a descriptive RuntimeError.
    """
    logger.info("Triggering LangGraph workflow for source: '%s'", source_name)
    reset_fallback_status(reset_quota=False)

    initial_state: AnalystState = {
        "raw_text": document_text,
        "document_source": source_name,
        "gemini_api_key": api_key,
        "gemini_model": model,
        "requirements": None,
        "validation": None,
        "user_stories": None,
        "architecture": None,
        "json_path": None,
        "markdown_path": None,
        "status": "started",
        "errors": [],
        "fallback_used": False,
        "fallback_message": None,
    }

    final_state = analyst_graph.invoke(initial_state)

    if final_state.get("status") == "failed" or not final_state.get("requirements"):
        err_msg = "; ".join(final_state.get("errors", ["Unknown agent workflow error"]))
        raise RuntimeError(f"Workflow execution stopped due to errors: {err_msg}")

    return FinalAnalysisResult(
        document_source=final_state.get("document_source", source_name),
        requirements=ExtractedRequirements.model_validate(final_state["requirements"]),
        validation=ValidationResult.model_validate(final_state["validation"]),
        user_stories=UserStoriesResult.model_validate(final_state["user_stories"]),
        architecture=ArchitectureProposal.model_validate(final_state["architecture"]),
        json_path=final_state.get("json_path"),
        markdown_path=final_state.get("markdown_path"),
        status=final_state.get("status", "completed"),
        errors=final_state.get("errors", []),
        fallback_used=is_fallback_activated() or bool(final_state.get("fallback_used")),
        fallback_message=get_fallback_message() or final_state.get("fallback_message"),
    )

