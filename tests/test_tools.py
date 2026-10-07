"""
Unit tests for deterministic tools: Document Reader, Requirement Validator, and Result Writer.
Does not require live external API keys.
"""

import os
import pytest
from app.config import SAMPLE_DATA_DIR
from app.tools.document_reader import (
    read_text_from_file_bytes,
    read_text_from_path,
    clean_extracted_text,
)
from app.tools.requirement_validator import run_deterministic_checks
from app.tools.result_writer import save_analysis_results, generate_markdown_report
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
    FinalAnalysisResult,
)


def test_txt_document_reading():
    """Test reading normal text document from bytes."""
    sample_content = b"System shall allow user to login.\nSystem shall process payments."
    extracted = read_text_from_file_bytes(sample_content, "requirements.txt")
    assert "System shall allow user to login." in extracted
    assert "System shall process payments." in extracted


def test_docx_document_reading():
    """Test extracting text from DOCX bytes."""
    import docx
    import io
    doc = docx.Document()
    doc.add_heading("Requirements Document", 0)
    doc.add_paragraph("The system shall support biometric authentication.")
    buffer = io.BytesIO()
    doc.save(buffer)
    docx_bytes = buffer.getvalue()

    extracted = read_text_from_file_bytes(docx_bytes, "test.docx")
    assert "Requirements Document" in extracted
    assert "The system shall support biometric authentication." in extracted


def test_pdf_document_reading():
    """Test extracting text from PDF bytes."""
    import pypdf
    import io
    writer = pypdf.PdfWriter()
    # Add a blank page with no text
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    pdf_bytes = buffer.getvalue()

    # Empty page should raise ValueError per our contract
    with pytest.raises(ValueError, match="did not yield any readable text"):
        read_text_from_file_bytes(pdf_bytes, "blank.pdf")


def test_read_sample_requirements_txt_from_disk():
    """Verify document_reader accurately extracts text from sample_requirements.txt."""
    path = os.path.join(SAMPLE_DATA_DIR, "sample_requirements.txt")
    assert os.path.exists(path), f"Sample TXT file must exist at {path}"
    extracted = read_text_from_path(path)

    assert len(extracted) > 1000
    assert "SmartClinic" in extracted
    assert "FUNCTIONAL REQUIREMENTS" in extracted.upper()
    assert "Patient Registration" in extracted
    assert "NON-FUNCTIONAL REQUIREMENTS" in extracted.upper()
    assert "AES-256" in extracted


def test_read_sample_requirements_docx_from_disk():
    """Verify document_reader accurately extracts text from sample_requirements.docx."""
    path = os.path.join(SAMPLE_DATA_DIR, "sample_requirements.docx")
    assert os.path.exists(path), f"Sample DOCX file must exist at {path}"
    extracted = read_text_from_path(path)

    assert len(extracted) > 1000
    assert "SmartClinic" in extracted
    assert "FUNCTIONAL REQUIREMENTS" in extracted.upper()
    assert "Patient Registration" in extracted
    assert "NON-FUNCTIONAL REQUIREMENTS" in extracted.upper()
    assert "AES-256" in extracted


def test_read_sample_requirements_pdf_from_disk():
    """Verify document_reader accurately extracts text from sample_requirements.pdf."""
    path = os.path.join(SAMPLE_DATA_DIR, "sample_requirements.pdf")
    assert os.path.exists(path), f"Sample PDF file must exist at {path}"
    extracted = read_text_from_path(path)

    assert len(extracted) > 1000
    assert "SmartClinic" in extracted
    assert "FUNCTIONAL REQUIREMENTS" in extracted.upper()
    assert "Patient Registration" in extracted
    assert "NON-FUNCTIONAL REQUIREMENTS" in extracted.upper()
    assert "AES-256" in extracted


def test_empty_document_validation():
    """Test that empty or whitespace-only documents raise descriptive ValueError."""
    with pytest.raises(ValueError, match="completely empty"):
        read_text_from_file_bytes(b"", "empty.txt")

    with pytest.raises(ValueError, match="whitespace or is empty"):
        read_text_from_file_bytes(b"   \n\t  \n  ", "spaces.txt")


def test_unsupported_file_extension():
    """Test that unsupported formats are rejected cleanly."""
    with pytest.raises(ValueError, match="Unsupported file format"):
        read_text_from_file_bytes(b"data", "binary.exe")


def test_clean_extracted_text():
    """Test whitespace normalization and stripping."""
    messy = "  Line 1   \n\n\n\n   Line 2  \n   "
    cleaned = clean_extracted_text(messy)
    assert cleaned == "Line 1\n\nLine 2"


def test_requirement_validator_detects_buzzwords():
    """Test deterministic validator flags unquantified buzzwords like 'fast' and 'user-friendly'."""
    reqs = ExtractedRequirements(
        system_goals=["Deliver food fast"],
        target_actors=["Customer"],
        functional_requirements=[
            RequirementItem(
                id="FR-01",
                category="Functional",
                title="Search Menu",
                description="The search engine must be extremely fast and reliable.",
                priority="High",
            )
        ],
        non_functional_requirements=[
            RequirementItem(
                id="NFR-01",
                category="Non-Functional",
                title="Usability",
                description="The interface must be user-friendly and intuitive for all users.",
                priority="Medium",
            )
        ],
        business_rules=[],
        constraints=[],
        entities_data=[],
        summary="Test summary",
    )

    report = run_deterministic_checks(reqs)
    assert report["quality_score"] < 10.0
    # Should detect 'fast' and 'user-friendly' or 'intuitive'
    warning_text = " ".join(report["warnings"])
    assert "fast" in warning_text
    assert "user-friendly" in warning_text


def test_result_writer_persistence_stable_filenames(tmp_path):
    """
    Test Result Writer Tool generates stable latest_analysis.json and latest_analysis.md files
    without timestamped filenames, and cleanly overwrites on subsequent runs.
    """
    dummy_analysis = FinalAnalysisResult(
        document_source="Unit Test Document",
        requirements=ExtractedRequirements(
            system_goals=["Automate clinic scheduling"],
            target_actors=["Patient", "Doctor"],
            functional_requirements=[
                RequirementItem(
                    id="FR-01",
                    category="Functional",
                    title="Book Appointment",
                    description="System records patient appointment slots.",
                    priority="High",
                )
            ],
            non_functional_requirements=[],
            business_rules=[],
            constraints=[],
            entities_data=["Appointment"],
            summary="Clinic appointment system",
        ),
        validation=ValidationResult(
            ambiguities=[
                AmbiguityItem(
                    requirement_reference="FR-01",
                    problem="Unspecified slot duration",
                    why_problematic="Scheduling collisions may occur",
                    suggested_clarification="Define 15-minute slot increments",
                    severity="Medium",
                )
            ],
            missing_information=[],
            conflicts_detected=[],
            deterministic_issues=[],
            overall_quality_score=8.5,
            validation_summary="Well structured specification with minor slot gap",
        ),
        user_stories=UserStoriesResult(
            stories=[
                UserStoryItem(
                    id="US-01",
                    role="Patient",
                    goal="book appointment online",
                    benefit="I avoid long clinic waiting queues",
                    user_story_text="As a Patient, I want to book an appointment online, so that I avoid long clinic waiting queues.",
                    acceptance_criteria=[
                        AcceptanceCriterion(
                            id="AC-01",
                            scenario="Slot reserved",
                            given="Patient selects a doctor",
                            when="Clicks available 10:00 AM slot",
                            then="Slot is locked for 10 minutes",
                        )
                    ],
                    priority="High",
                )
            ],
            summary="1 core user story",
        ),
        architecture=ArchitectureProposal(
            architecture_style="Modular Monolith",
            components=[
                ArchitectureComponent(
                    name="Appointment Service",
                    layer="Backend",
                    technology_recommendation="FastAPI",
                    responsibility="Manage appointment slots",
                )
            ],
            database_recommendations=["PostgreSQL"],
            authentication_strategy="JWT tokens",
            external_services=[],
            communication_flow=["Frontend communicates with Backend"],
            rationale="Simple MVP needs no microservice overhead",
            text_diagram="[ UI ] -> [ API ] -> [ DB ]",
        ),
    )

    # First run
    json_path, md_path = save_analysis_results(dummy_analysis, output_dir=str(tmp_path))

    assert os.path.basename(json_path) == "latest_analysis.json"
    assert os.path.basename(md_path) == "latest_analysis.md"
    assert os.path.exists(json_path)
    assert os.path.exists(md_path)
    assert os.path.getsize(json_path) > 0
    assert os.path.getsize(md_path) > 0

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    assert "Intelligent Software Requirement Analysis Report" in md_text
    assert "FR-01" in md_text
    assert "As a Patient, I want to book an appointment online" in md_text

    # Second run should overwrite, NOT create new files
    json_path2, md_path2 = save_analysis_results(dummy_analysis, output_dir=str(tmp_path))
    assert json_path2 == json_path
    assert md_path2 == md_path

    # Check directory contents: must have ONLY the 2 latest files
    files_in_dir = os.listdir(tmp_path)
    assert sorted(files_in_dir) == ["latest_analysis.json", "latest_analysis.md"]


def test_pdf_report_generator_from_model():
    """Verify that generate_pdf_report produces valid PDF bytes from FinalAnalysisResult model."""
    from app.tools.pdf_generator import generate_pdf_report

    dummy_analysis = FinalAnalysisResult(
        document_source="sample_requirements.txt",
        requirements=ExtractedRequirements(
            system_goals=["Automate clinic workflow"],
            target_actors=["Patient", "Doctor"],
            functional_requirements=[
                RequirementItem(
                    id="FR-01",
                    category="Functional",
                    title="Book Appointment",
                    description="Allow patients to book slots online.",
                    priority="High",
                )
            ],
            non_functional_requirements=[
                RequirementItem(
                    id="NFR-01",
                    category="Non-Functional",
                    title="Response Time",
                    description="Booking API responds under 500ms.",
                    priority="Medium",
                )
            ],
            business_rules=["Cancel before 2 hours"],
            constraints=["HIPAA compliant"],
            entities_data=["Patient", "Appointment"],
            summary="Clinic appointment booking system",
        ),
        validation=ValidationResult(
            ambiguities=[],
            missing_information=[],
            conflicts_detected=[],
            deterministic_issues=[],
            overall_quality_score=9.2,
            validation_summary="Well specified requirements",
        ),
        user_stories=UserStoriesResult(
            stories=[
                UserStoryItem(
                    id="US-01",
                    role="Patient",
                    goal="book appointment online",
                    benefit="I save phone waiting time",
                    user_story_text="As a Patient, I want to book an appointment online, so that I save phone waiting time.",
                    acceptance_criteria=[
                        AcceptanceCriterion(
                            id="AC-01",
                            scenario="Successful slot booking",
                            given="Patient is logged in",
                            when="Selects available slot and clicks confirm",
                            then="Appointment is created and confirmation SMS is sent",
                        )
                    ],
                    priority="High",
                )
            ],
            summary="1 user story with acceptance criteria",
        ),
        architecture=ArchitectureProposal(
            architecture_style="Modular Monolith with REST API",
            components=[
                ArchitectureComponent(
                    name="Appointment Service",
                    layer="Backend",
                    technology_recommendation="FastAPI",
                    responsibility="Manage appointment slots",
                )
            ],
            database_recommendations=["PostgreSQL"],
            authentication_strategy="JWT tokens",
            external_services=[],
            communication_flow=["Frontend communicates with Backend"],
            rationale="Simple MVP needs no microservice overhead",
            text_diagram="[ UI ] -> [ API ] -> [ DB ]",
        ),
    )

    pdf_bytes = generate_pdf_report(dummy_analysis)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_report_generator_from_dict():
    """Verify that generate_pdf_report also accepts raw dictionary input."""
    from app.tools.pdf_generator import generate_pdf_report

    raw_dict = {
        "document_source": "test_doc.txt",
        "requirements": {
            "system_goals": ["Goal 1"],
            "target_actors": ["User"],
            "functional_requirements": [
                {
                    "id": "FR-01",
                    "category": "Functional",
                    "title": "Login",
                    "description": "User login with password",
                    "priority": "High",
                }
            ],
            "non_functional_requirements": [],
            "business_rules": [],
            "constraints": [],
            "entities_data": [],
            "summary": "Summary of system",
        },
        "validation": {
            "ambiguities": [],
            "missing_information": [],
            "conflicts_detected": [],
            "deterministic_issues": [],
            "overall_quality_score": 8.0,
            "validation_summary": "Passed",
        },
        "user_stories": {
            "stories": [],
            "summary": "No stories",
        },
        "architecture": {
            "architecture_style": "Monolith",
            "components": [],
            "database_recommendations": [],
            "authentication_strategy": "Token",
            "external_services": [],
            "communication_flow": [],
            "rationale": "Simple",
            "text_diagram": "[ UI ] -> [ API ]",
        },
        "status": "completed",
    }

    pdf_bytes = generate_pdf_report(raw_dict)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")
