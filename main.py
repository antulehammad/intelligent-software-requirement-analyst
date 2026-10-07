"""
Main FastAPI Application for Intelligent Software Requirement Analyst.
Provides RESTful endpoints for document upload, text analysis, and report generation.
"""

import os
import logging
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import (
    PORT,
    HOST,
    GEMINI_MODEL,
    OUTPUT_DIR,
    SAMPLE_DATA_DIR,
    is_api_key_valid,
    get_masked_api_key,
    reload_env,
)

from app.models.schemas import (
    TextAnalysisRequest,
    AnalysisApiResponse,
    FinalAnalysisResult,
)
from app.tools.document_reader import read_text_from_file_bytes
from app.graph.workflow import run_analyst_workflow

# Configure logging
logger = logging.getLogger("RequirementAnalyst.API")

# Initialize FastAPI Application
app = FastAPI(
    title="Intelligent Software Requirement Analyst API",
    description="Multi-Agent System (PS-2) powered by LangGraph & Google Gemini to extract requirements, validate ambiguities, generate user stories, and propose software architecture.",
    version="1.0.0",
)

# Enable CORS for local Streamlit and frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
async def root():
    """Health check and system capabilities endpoint."""
    reload_env()
    from app.config import GEMINI_MODEL as CURRENT_MODEL
    has_key = is_api_key_valid()
    return {
        "status": "online",
        "service": "Intelligent Software Requirement Analyst",
        "problem_statement": "PS-2 (Software Engineering & Development)",
        "gemini_model": CURRENT_MODEL,
        "api_key_configured": has_key,
        "api_key_masked": get_masked_api_key(),
        "available_agents": [
            "Agent 1: Requirement Extraction Agent",
            "Agent 2: Ambiguity & Validation Agent (with Deterministic Tool)",
            "Agent 3: User Story & Acceptance Criteria Agent",
            "Agent 4: Architecture Proposal Agent",
        ],
        "active_tools": [
            "Document Reader Tool (PDF, DOCX, TXT)",
            "Requirement Validation Tool (Heuristic & Buzzword Auditor)",
            "Result Writer Tool (JSON & Markdown Exporter)",
        ],
    }


@app.get("/api/sample", tags=["Sample Data"])
async def get_sample_requirements():
    """Retrieve pre-loaded realistic sample requirements document."""
    sample_path = os.path.join(SAMPLE_DATA_DIR, "sample_requirements.txt")
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail="Sample requirements file not found.")
    
    with open(sample_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    return {
        "filename": "sample_requirements.txt",
        "title": "SmartClinic Appointment Management System",
        "text": content,
    }


@app.post("/api/analyze-text", response_model=AnalysisApiResponse, tags=["Analysis"])
async def analyze_text(payload: TextAnalysisRequest):
    """
    Process raw requirements text through the LangGraph 4-agent workflow.
    """
    reload_env()
    from app.config import GEMINI_MODEL as DEFAULT_MODEL
    logger.info("Received request for text analysis. Text length: %d", len(payload.text))

    if not payload.text or len(payload.text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requirements text must be at least 10 characters long.",
        )

    # Determine effective API key and model
    effective_key = payload.gemini_api_key if payload.gemini_api_key and is_api_key_valid(payload.gemini_api_key) else None
    if not effective_key and not is_api_key_valid():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GEMINI_API_KEY is not configured or is a placeholder. Please set your Gemini API key in your .env file or UI settings.",
        )

    effective_model = payload.gemini_model or DEFAULT_MODEL

    try:
        result = run_analyst_workflow(
            document_text=payload.text,
            source_name=payload.document_name or "Direct Input",
            api_key=effective_key,
            model=effective_model,
        )
        return AnalysisApiResponse(
            success=True,
            message="Multi-agent requirements analysis completed successfully.",
            data=result,
        )
    except Exception as e:
        logger.error("Analysis failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Requirement analysis workflow failed: {str(e)}",
        )


@app.post("/api/analyze-file", response_model=AnalysisApiResponse, tags=["Analysis"])
async def analyze_file(
    file: UploadFile = File(...),
    custom_api_key: Optional[str] = Form(None),
    custom_gemini_model: Optional[str] = Form(None),
):
    """
    Upload and analyze a PDF, DOCX, or TXT software requirements document.
    """
    reload_env()
    from app.config import GEMINI_MODEL as DEFAULT_MODEL
    filename = file.filename or "uploaded_document"
    logger.info("Received file upload: %s", filename)

    # Validate file extension
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".txt", ".pdf", ".docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Please upload a .pdf, .docx, or .txt file.",
        )

    # Verify API key availability
    effective_key = custom_api_key if custom_api_key and is_api_key_valid(custom_api_key) else None
    if not effective_key and not is_api_key_valid():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GEMINI_API_KEY is not configured. Please supply a valid Gemini API key in your .env file or form input.",
        )

    effective_model = custom_gemini_model or DEFAULT_MODEL

    try:
        file_bytes = await file.read()
        extracted_text = read_text_from_file_bytes(file_bytes, filename)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file '{filename}': {str(e)}",
        )

    try:
        result = run_analyst_workflow(
            document_text=extracted_text,
            source_name=filename,
            api_key=effective_key,
            model=effective_model,
        )
        return AnalysisApiResponse(
            success=True,
            message=f"Analysis of '{filename}' completed successfully via 4-agent LangGraph workflow.",
            data=result,
        )

    except Exception as e:
        logger.error("Workflow error processing file '%s': %s", filename, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing agent workflow: {str(e)}",
        )


@app.get("/api/download/{file_type}/{filename}", tags=["Download"])
async def download_file(file_type: str, filename: str):
    """
    Download generated JSON or Markdown analysis report from output directory.
    """
    # Sanitize filename against directory traversal
    safe_name = os.path.basename(filename)
    target_path = os.path.join(OUTPUT_DIR, safe_name)

    if not os.path.exists(target_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file '{safe_name}' was not found.",
        )

    media_types = {
        "json": "application/json",
        "markdown": "text/markdown",
        "md": "text/markdown",
    }
    media_type = media_types.get(file_type.lower(), "application/octet-stream")

    return FileResponse(
        path=target_path,
        media_type=media_type,
        filename=safe_name,
    )


if __name__ == "__main__":
    import uvicorn
    print(f"Starting Intelligent Software Requirement Analyst API on http://{HOST}:{PORT}")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
