"""
Unit tests for LangGraph workflow structure and orchestration logic.
Ensures graph integrity, node registration, and state updates without requiring live API keys.
"""

from unittest.mock import patch, MagicMock
from app.graph.workflow import build_analyst_graph, AnalystState
from app.models.schemas import (
    RequirementItem,
    ExtractedRequirements,
    AmbiguityItem,
    ValidationResult,
    AcceptanceCriterion,
    UserStoryItem,
    UserStoriesResult,
    ArchitectureComponent,
    ArchitectureProposal,
)


def test_graph_compilation_and_nodes():
    """Verify that the LangGraph StateGraph builds and contains all required agent nodes."""
    graph = build_analyst_graph()
    assert graph is not None

    # Inspect registered nodes in LangGraph compiled graph
    node_keys = list(graph.nodes.keys())
    assert "extraction" in node_keys
    assert "validation" in node_keys
    assert "user_stories" in node_keys
    assert "architecture" in node_keys
    assert "result_writer" in node_keys


@patch("app.graph.workflow.extract_requirements")
@patch("app.graph.workflow.validate_requirements")
@patch("app.graph.workflow.generate_user_stories")
@patch("app.graph.workflow.propose_architecture")
@patch("app.graph.workflow.get_gemini_client")
def test_mocked_end_to_end_workflow(
    mock_get_client,
    mock_arch,
    mock_stories,
    mock_val,
    mock_extract,
    tmp_path,
):
    """Test full sequential workflow execution with mocked agents."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Mock Agent 1 Output
    mock_extract.return_value = ExtractedRequirements(
        system_goals=["E-commerce checkout"],
        target_actors=["Buyer"],
        functional_requirements=[
            RequirementItem(
                id="FR-01",
                category="Functional",
                title="Add to cart",
                description="User adds items to their shopping cart.",
                priority="High",
            )
        ],
        non_functional_requirements=[],
        business_rules=[],
        constraints=[],
        entities_data=["Cart"],
        summary="Cart checkout system",
    )

    # Mock Agent 2 Output
    mock_val.return_value = ValidationResult(
        ambiguities=[
            AmbiguityItem(
                requirement_reference="FR-01",
                problem="No cart expiration defined",
                why_problematic="Inventory may be locked forever",
                suggested_clarification="Define 30 minute reservation window",
                severity="Medium",
            )
        ],
        missing_information=[],
        conflicts_detected=[],
        deterministic_issues=[],
        overall_quality_score=8.5,
        validation_summary="Well specified with minor cart timeout gap",
    )

    # Mock Agent 3 Output
    mock_stories.return_value = UserStoriesResult(
        stories=[
            UserStoryItem(
                id="US-01",
                role="Buyer",
                goal="add items to cart",
                benefit="I can purchase them together",
                user_story_text="As a Buyer, I want to add items to cart, so that I can purchase them together.",
                acceptance_criteria=[
                    AcceptanceCriterion(
                        id="AC-01",
                        scenario="Item added",
                        given="Buyer is on product page",
                        when="Clicks Add to Cart",
                        then="Cart badge count increments by 1",
                    )
                ],
                priority="High",
            )
        ],
        summary="1 story",
    )

    # Mock Agent 4 Output
    mock_arch.return_value = ArchitectureProposal(
        architecture_style="Client-Server REST",
        components=[
            ArchitectureComponent(
                name="Cart Service",
                layer="Backend",
                technology_recommendation="FastAPI",
                responsibility="Handles cart state",
            )
        ],
        database_recommendations=["PostgreSQL"],
        authentication_strategy="JWT",
        external_services=[],
        communication_flow=["Client -> Cart API -> DB"],
        rationale="Simple and effective for e-commerce MVP",
        text_diagram="[ Client ] -> [ API ] -> [ DB ]",
    )

    # Run compiled graph
    graph = build_analyst_graph()

    initial_state: AnalystState = {
        "raw_text": "System shall allow buyer to add items to cart.",
        "document_source": "test_doc.txt",
        "gemini_api_key": "test_mock_api_key_12345",
        "gemini_model": "gemini-3.8-flash",
        "requirements": None,
        "validation": None,
        "user_stories": None,
        "architecture": None,
        "json_path": None,
        "markdown_path": None,
        "status": "started",
        "errors": [],
    }

    final_state = graph.invoke(initial_state)

    # Verify state progression
    assert final_state["status"] == "completed"
    assert final_state["requirements"] is not None
    assert final_state["validation"] is not None
    assert final_state["user_stories"] is not None
    assert final_state["architecture"] is not None
    assert final_state["json_path"] is not None
    assert final_state["markdown_path"] is not None
    assert final_state["json_path"].endswith("latest_analysis.json")
    assert final_state["markdown_path"].endswith("latest_analysis.md")


@patch("app.graph.workflow.get_gemini_client")
def test_workflow_503_immediate_fallback(mock_get_client, tmp_path):
    """
    Test full LangGraph workflow execution when Agent 1 hits 503:
    1. Agent 1 hits 503 on gemini-3.8-flash, immediately falls back to gemini-3.5-flash-lite.
    2. Agents 2, 3, and 4 directly use gemini-3.5-flash-lite without attempting gemini-3.8-flash.
    3. Workflow completes with fallback_used=True and proper fallback notice.
    """
    import json
    from app.agents.llm_util import reset_fallback_status
    from app.graph.workflow import run_analyst_workflow

    reset_fallback_status()

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Minimal valid payloads for each agent's schema
    payload_a1 = {
        "system_goals": ["Goal 1"],
        "target_actors": ["User"],
        "functional_requirements": [
            {"id": "FR-01", "category": "Functional", "title": "Login", "description": "User logs in", "priority": "High"}
        ],
        "non_functional_requirements": [],
        "business_rules": [],
        "constraints": [],
        "entities_data": [],
        "summary": "Summary",
    }
    payload_a2 = {
        "ambiguities": [],
        "missing_information": [],
        "conflicts_detected": [],
        "deterministic_issues": [],
        "overall_quality_score": 9.0,
        "validation_summary": "Good",
    }
    payload_a3 = {
        "stories": [
            {
                "id": "US-01",
                "role": "User",
                "goal": "Login",
                "benefit": "Access account",
                "user_story_text": "As a User, I want to Login, so that Access account.",
                "acceptance_criteria": [
                    {"id": "AC-01", "scenario": "Success", "given": "Credentials", "when": "Submit", "then": "Logged in"}
                ],
                "priority": "High",
            }
        ],
        "summary": "1 story",
    }
    payload_a4 = {
        "architecture_style": "Monolith",
        "components": [
            {"name": "Auth", "layer": "Backend", "technology_recommendation": "Python", "responsibility": "Auth"}
        ],
        "database_recommendations": ["PostgreSQL"],
        "authentication_strategy": "JWT",
        "external_services": [],
        "communication_flow": ["UI -> API"],
        "rationale": "Simple",
        "text_diagram": "[ UI ] -> [ API ]",
    }

    mock_resp_fb1 = MagicMock(text=json.dumps(payload_a1))
    mock_resp_fb2 = MagicMock(text=json.dumps(payload_a2))
    mock_resp_fb3 = MagicMock(text=json.dumps(payload_a3))
    mock_resp_fb4 = MagicMock(text=json.dumps(payload_a4))

    # Total 5 generate_content calls across 4 agents:
    # Agent 1: gemini-3.8-flash (503) -> gemini-3.5-flash-lite (success)
    # Agent 2: directly gemini-3.5-flash-lite (success)
    # Agent 3: directly gemini-3.5-flash-lite (success)
    # Agent 4: directly gemini-3.5-flash-lite (success)
    mock_client.models.generate_content.side_effect = [
        Exception("503 UNAVAILABLE: Model is temporarily overloaded."),
        mock_resp_fb1,
        mock_resp_fb2,
        mock_resp_fb3,
        mock_resp_fb4,
    ]

    result = run_analyst_workflow(
        document_text="The system shall allow users to log in with email and password.",
        source_name="workflow_test.txt",
        api_key="mock_test_key",
        model="gemini-3.8-flash",
    )

    assert result is not None
    assert result.fallback_used is True
    assert "fallback model" in result.fallback_message.lower()

    # Total calls: exactly 5
    assert mock_client.models.generate_content.call_count == 5
    calls = mock_client.models.generate_content.call_args_list
    assert calls[0].kwargs["model"] == "gemini-3.8-flash"      # Agent 1 primary (hit 503)
    assert calls[1].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 1 fallback
    assert calls[2].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 2 direct fallback
    assert calls[3].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 3 direct fallback
    assert calls[4].kwargs["model"] == "gemini-3.5-flash-lite"  # Agent 4 direct fallback

