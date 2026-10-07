"""
Streamlit Web User Interface for Intelligent Software Requirement Analyst.
Provides an interactive dashboard for document upload, real-time agent execution tracking,
and multi-tab exploration of requirements, ambiguities, user stories, and architecture.
"""

import os
import sys
import json
import requests
import streamlit as st

# Configure page settings
st.set_page_config(
    page_title="Intelligent Software Requirement Analyst",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure project root is on sys.path so app modules are always importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Explicitly load project root .env
from dotenv import load_dotenv
ENV_FILE_PATH = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(ENV_FILE_PATH):
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)

from app.config import (
    FASTAPI_BACKEND_URL,
    SAMPLE_DATA_DIR,
    OUTPUT_DIR,
    is_api_key_valid,
    get_masked_api_key,
    reload_env,
)

# App Constants & Defaults
BACKEND_URL = FASTAPI_BACKEND_URL
SAMPLE_FILE_PATH = os.path.join(SAMPLE_DATA_DIR, "sample_requirements.txt")

# ---------------------------------------------------------
# Sidebar: Configuration & Academic Metadata
# ---------------------------------------------------------

with st.sidebar:
    st.image(
        "https://raw.githubusercontent.com/google/material-design-icons/master/png/action/assignment/materialicons/48dp/2x/baseline_assignment_black_48dp.png",
        width=48,
    )
    st.title("Project Details")
    st.markdown(
        "- **Problem Statement:** PS-2  \n"
        "- **Domain:** Software Engineering & AI  \n"
        "- **Architecture:** Multi-Agent (LangGraph)  \n"
        "- **Student:** Mohammed Hammad Antule  \n"
        "- **Roll No.:** 02"
    )
    
    st.divider()
    st.subheader("⚙️ Gemini LLM Settings")

    # Refresh environment variables from root .env
    reload_env()
    from app.config import GEMINI_API_KEY as ENV_KEY, GEMINI_MODEL as ENV_MODEL

    env_key_available = is_api_key_valid(ENV_KEY)

    # Optional manual override input (defaults to empty)
    user_override_key = st.text_input(
        "Override Gemini API Key (Optional)",
        value="",
        type="password",
        placeholder="Leave blank to use key from .env",
        help="By default, the key from the root .env file is used automatically. Enter a key here only if you wish to override it.",
    )

    # Resolve effective API key
    if user_override_key.strip():
        effective_api_key = user_override_key.strip()
        st.info(f"🔑 Using Manual Override ({get_masked_api_key(effective_api_key)})")
    elif env_key_available:
        effective_api_key = ENV_KEY
        st.success(f"✅ Loaded from .env ({get_masked_api_key(ENV_KEY)})")
    else:
        effective_api_key = None
        st.warning("⚠️ Gemini API Key not set. Add it in .env or enter above.")

    # Model selector with gemini-3.8-flash default
    model_options = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    default_idx = 0
    if ENV_MODEL in model_options:
        default_idx = model_options.index(ENV_MODEL)

    model_name = st.selectbox(
        "Configured Gemini Model",
        options=model_options,
        index=default_idx,
        help="Configured via GEMINI_MODEL in .env",
    )



    st.divider()
    st.subheader("🤖 Specialized Agents")
    st.markdown(
        """
        1. **Extraction Agent** (Entities, Goals, FRs, NFRs)
        2. **Validation Agent** (Deterministic + LLM Ambiguity)
        3. **User Story Agent** (Agile BDD Given/When/Then)
        4. **Architecture Agent** (Components, Stack, Diagrams)
        """
    )
    
    st.divider()
    st.caption("College MVP Demo | Python 3.11+ | LangGraph | FastAPI | Streamlit")


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def load_sample_text() -> str:
    """Read sample requirements file."""
    if os.path.exists(SAMPLE_FILE_PATH):
        with open(SAMPLE_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def run_analysis_direct(text: str, filename: str, api_key: str, model: str):
    """Fallback runner if FastAPI is not active: runs the workflow directly."""
    from app.graph.workflow import run_analyst_workflow
    return run_analyst_workflow(
        document_text=text,
        source_name=filename,
        api_key=api_key,
        model=model,
    )


# ---------------------------------------------------------
# Main UI Layout
# ---------------------------------------------------------

st.title("Intelligent Software Requirement Analyst")
st.markdown(
    """
    **Autonomous Multi-Agent System (PS-2)** for extracting software requirements, 
    detecting ambiguities, synthesizing agile user stories with acceptance criteria, 
    and generating basic software architecture proposals.
    """
)

# Input Section
st.subheader("📄 Input Requirements Document")

input_mode = st.radio(
    "Select Input Method:",
    options=["Paste Requirements Text", "Upload File (PDF / DOCX / TXT)"],
    horizontal=True,
)

document_text = ""
document_name = "Direct Input"
uploaded_file_bytes = None

if input_mode == "Paste Requirements Text":
    col_btn, col_clear = st.columns([1, 4])
    with col_btn:
        if st.button("📋 Load Sample (SmartClinic SRS)", use_container_width=True):
            st.session_state["pasted_text"] = load_sample_text()
            st.success("Sample requirements loaded!")

    document_text = st.text_area(
        "Enter natural language requirements specification:",
        value=st.session_state.get("pasted_text", ""),
        height=220,
        placeholder="e.g. The system shall allow users to register and order products...",
    )
else:
    uploaded_file = st.file_uploader(
        "Upload software requirements document (.pdf, .docx, .txt)",
        type=["pdf", "docx", "txt"],
    )
    if uploaded_file is not None:
        document_name = uploaded_file.name
        # Build unique signature for the uploaded file instance
        file_sig = f"{uploaded_file.name}_{uploaded_file.size}_{getattr(uploaded_file, 'file_id', '')}"

        # Only read/extract if this file signature has not been processed yet
        if (
            st.session_state.get("cached_file_sig") != file_sig
            or "cached_document_text" not in st.session_state
        ):
            try:
                from app.tools.document_reader import read_text_from_file_bytes
                uploaded_file_bytes = uploaded_file.getvalue()
                extracted_text = read_text_from_file_bytes(uploaded_file_bytes, document_name)
                st.session_state["cached_file_sig"] = file_sig
                st.session_state["cached_document_text"] = extracted_text
                st.session_state["cached_document_name"] = document_name
                st.session_state["cached_read_error"] = None
            except Exception as e:
                st.session_state["cached_file_sig"] = file_sig
                st.session_state["cached_document_text"] = ""
                st.session_state["cached_document_name"] = document_name
                st.session_state["cached_read_error"] = str(e)

        # Retrieve text from session state cache without re-reading the file
        document_text = st.session_state.get("cached_document_text", "")
        document_name = st.session_state.get("cached_document_name", uploaded_file.name)
        cached_err = st.session_state.get("cached_read_error")

        if cached_err:
            st.error(f"Error reading uploaded file: {cached_err}")
            document_text = ""
        elif document_text:
            st.success(f"Successfully read **{document_name}** ({len(document_text)} characters extracted)")
            with st.expander("Preview Extracted Document Text", expanded=False):
                st.text(document_text[:1500] + ("..." if len(document_text) > 1500 else ""))
    else:
        # Clear cache when file is removed
        st.session_state.pop("cached_file_sig", None)
        st.session_state.pop("cached_document_text", None)
        st.session_state.pop("cached_document_name", None)
        st.session_state.pop("cached_read_error", None)

# Analysis Action Button
st.write("")
col_run, col_status = st.columns([1, 3])

with col_run:
    analyze_clicked = st.button("🚀 Analyze Requirements", type="primary", use_container_width=True)

if analyze_clicked:
    if not document_text or len(document_text.strip()) < 10:
        st.error("Please provide requirement text or an uploaded document before analyzing.")
    elif not effective_api_key:
        st.error("Gemini API Key is missing. Please configure it in .env or the sidebar.")
    else:
        with st.status("Running Multi-Agent Orchestration Workflow...", expanded=True) as status_box:
            st.write("🔍 **Agent 1:** Extracting Functional & Non-Functional Requirements...")
            st.write("⚠️ **Agent 2:** Auditing Ambiguities & Running Deterministic Checks...")
            st.write("📖 **Agent 3:** Generating Agile User Stories & Given/When/Then Criteria...")
            st.write("🏗️ **Agent 4:** Formulating Software Architecture & Diagrams...")
            st.write("💾 **Tool Execution:** Persisting JSON and Markdown reports...")

            try:
                # Attempt to query FastAPI backend first
                backend_success = False
                api_response_data = None
                
                try:
                    res = requests.get(f"{BACKEND_URL}/", timeout=2)
                    if res.status_code == 200:
                        # Backend is alive, dispatch to FastAPI
                        payload = {
                            "text": document_text,
                            "document_name": document_name,
                            "gemini_api_key": effective_api_key,
                            "gemini_model": model_name,
                        }
                        api_res = requests.post(
                            f"{BACKEND_URL}/api/analyze-text",
                            json=payload,
                            timeout=120,
                        )

                        if api_res.status_code == 200:
                            json_body = api_res.json()
                            api_response_data = json_body.get("data")
                            backend_success = True
                except Exception:
                    # Backend unreachable, fall through to direct workflow
                    backend_success = False

                if not backend_success or not api_response_data:
                    # Run direct in-process LangGraph workflow
                    result_obj = run_analysis_direct(
                        text=document_text,
                        filename=document_name,
                        api_key=effective_api_key,
                        model=model_name,
                    )
                    api_response_data = result_obj.model_dump()

                st.session_state["analysis_result"] = api_response_data
                if api_response_data.get("fallback_used"):
                    st.info("⚠️ Primary Gemini model unavailable. Using fallback model.")
                status_box.update(label="✅ Multi-Agent Analysis Completed Successfully!", state="complete")
                st.balloons()
            except Exception as e:
                status_box.update(label="❌ Analysis Failed", state="error")
                st.error(f"Execution Error: {str(e)}")


# ---------------------------------------------------------
# Display Analysis Results in Tabs
# ---------------------------------------------------------

if "analysis_result" in st.session_state and st.session_state["analysis_result"]:
    result = st.session_state["analysis_result"]
    reqs = result.get("requirements", {})
    val = result.get("validation", {})
    stories = result.get("user_stories", {})
    arch = result.get("architecture", {})

    st.divider()
    st.header("📊 Multi-Agent Analysis Output")

    if result.get("fallback_used"):
        st.warning("⚠️ Primary Gemini model unavailable. Using fallback model.")

    # Overview Metrics Row

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Quality Score", f"{val.get('overall_quality_score', 0)}/10")
    with m2:
        st.metric("Functional Reqs", len(reqs.get("functional_requirements", [])))
    with m3:
        st.metric("Non-Functional Reqs", len(reqs.get("non_functional_requirements", [])))
    with m4:
        st.metric("Ambiguities Detected", len(val.get("ambiguities", [])))
    with m5:
        st.metric("User Stories", len(stories.get("stories", [])))

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 Extracted Requirements",
        "⚠️ Ambiguities & Validation",
        "📖 User Stories",
        "✅ Acceptance Criteria",
        "🏗️ Architecture Proposal",
        "📥 Complete Analysis & Export",
    ])

    # TAB 1: EXTRACTED REQUIREMENTS
    with tab1:
        st.subheader("Executive Summary & System Goals")
        if reqs.get("summary"):
            st.info(reqs["summary"])

        col_g, col_a = st.columns(2)
        with col_g:
            st.markdown("### 🎯 System Goals")
            for g in reqs.get("system_goals", []):
                st.markdown(f"- {g}")
        with col_a:
            st.markdown("### 👥 Target Actors & Personas")
            for a in reqs.get("target_actors", []):
                st.markdown(f"- **{a}**")

        st.divider()
        st.markdown("### ⚙️ Functional Requirements")
        fr_list = reqs.get("functional_requirements", [])
        if fr_list:
            for fr in fr_list:
                with st.expander(f"**{fr.get('id')}**: {fr.get('title')} [{fr.get('priority', 'Medium')} Priority]"):
                    st.write(fr.get("description"))
        else:
            st.write("No functional requirements listed.")

        st.divider()
        st.markdown("### 🛡️ Non-Functional Requirements")
        nfr_list = reqs.get("non_functional_requirements", [])
        if nfr_list:
            for nfr in nfr_list:
                with st.expander(f"**{nfr.get('id')}**: {nfr.get('title')} [{nfr.get('priority', 'Medium')} Priority]"):
                    st.write(nfr.get("description"))

        if reqs.get("business_rules"):
            st.divider()
            st.markdown("### 📜 Business Rules & Constraints")
            col_b, col_c = st.columns(2)
            with col_b:
                st.markdown("**Business Rules:**")
                for br in reqs.get("business_rules", []):
                    st.markdown(f"- {br}")
            with col_c:
                st.markdown("**Constraints:**")
                for c in reqs.get("constraints", []):
                    st.markdown(f"- {c}")

    # TAB 2: AMBIGUITIES & VALIDATION
    with tab2:
        st.subheader("Requirement Quality & Ambiguity Audit")
        if val.get("validation_summary"):
            st.warning(f"**Validation Summary:** {val['validation_summary']}")

        amb_list = val.get("ambiguities", [])
        st.markdown(f"### 🚩 Detected Ambiguities ({len(amb_list)})")
        if amb_list:
            for idx, item in enumerate(amb_list, start=1):
                severity_color = "red" if item.get("severity") == "High" else "orange"
                st.markdown(f"#### {idx}. Ref: `{item.get('requirement_reference')}` (:{severity_color}[{item.get('severity')} Severity])")
                st.markdown(f"- **Problem:** {item.get('problem')}")
                st.markdown(f"- **Why it is problematic:** {item.get('why_problematic')}")
                st.markdown(f"- **💡 Suggested Clarification:** {item.get('suggested_clarification')}")
                st.write("")
        else:
            st.success("No critical ambiguities detected.")

        col_m, col_conf = st.columns(2)
        with col_m:
            st.markdown("### ⚠️ Missing Information")
            for m in val.get("missing_information", []):
                st.markdown(f"- {m}")
        with col_conf:
            st.markdown("### ⚡ Conflicting Requirements")
            conf_list = val.get("conflicts_detected", [])
            if conf_list:
                for conf in conf_list:
                    st.markdown(f"- {conf}")
            else:
                st.write("No direct conflicts identified.")

        if val.get("deterministic_issues"):
            st.divider()
            st.markdown("### 🔍 Automated Tool Findings (Deterministic Validator)")
            for det in val.get("deterministic_issues", []):
                st.markdown(f"- `{det}`")

    # TAB 3: USER STORIES
    with tab3:
        st.subheader("Agile User Stories")
        if stories.get("summary"):
            st.caption(stories["summary"])

        story_list = stories.get("stories", [])
        for story in story_list:
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"### `{story.get('id')}`: {story.get('role')}")
                with c2:
                    st.markdown(f"**Priority:** `{story.get('priority', 'Medium')}`")

                st.info(f"**{story.get('user_story_text')}**")
                st.markdown(f"- **Goal:** {story.get('goal')}")
                st.markdown(f"- **Benefit:** {story.get('benefit')}")

    # TAB 4: ACCEPTANCE CRITERIA
    with tab4:
        st.subheader("BDD Acceptance Criteria (Given / When / Then)")
        story_list = stories.get("stories", [])
        for story in story_list:
            ac_list = story.get("acceptance_criteria", [])
            if ac_list:
                st.markdown(f"### `{story.get('id')}`: {story.get('role')}")
                for ac in ac_list:
                    with st.expander(f"**{ac.get('id')} - {ac.get('scenario')}**", expanded=True):
                        st.markdown(f"- **Given** {ac.get('given')}")
                        st.markdown(f"- **When** {ac.get('when')}")
                        st.markdown(f"- **Then** {ac.get('then')}")
                st.write("")

    # TAB 5: ARCHITECTURE PROPOSAL
    with tab5:
        st.subheader("Software Architecture Proposal")
        st.markdown(f"**Recommended Architecture Style:** `{arch.get('architecture_style')}`")
        if arch.get("rationale"):
            st.markdown(f"**Why this architecture fits:**  \n{arch.get('rationale')}")

        st.markdown("### 📐 Text-Based Architecture Diagram")
        diagram_text = arch.get("text_diagram", "")
        st.code(diagram_text, language="text")

        st.markdown("### 🧩 Main Architecture Components")
        components = arch.get("components", [])
        if components:
            for comp in components:
                with st.expander(f"**{comp.get('name')}** ({comp.get('layer')})"):
                    st.markdown(f"- **Technology:** `{comp.get('technology_recommendation')}`")
                    st.markdown(f"- **Responsibility:** {comp.get('responsibility')}")

        col_d, col_a = st.columns(2)
        with col_d:
            st.markdown("### 🗄️ Database & Storage")
            for db in arch.get("database_recommendations", []):
                st.markdown(f"- {db}")
        with col_a:
            st.markdown("### 🔐 Authentication & Security")
            st.write(arch.get("authentication_strategy", "Standard Token Authentication"))

        if arch.get("communication_flow"):
            st.markdown("### 🔄 Component Communication Flow")
            for flow in arch.get("communication_flow", []):
                st.markdown(f"- {flow}")

    # TAB 6: COMPLETE ANALYSIS & EXPORT
    with tab6:
        st.subheader("📥 Export & Download Deliverables")
        from app.tools.result_writer import generate_markdown_report
        from app.models.schemas import FinalAnalysisResult

        # Prepare downloads
        json_str = json.dumps(result, indent=2)
        
        try:
            pydantic_res = FinalAnalysisResult.model_validate(result)
            md_str = generate_markdown_report(pydantic_res)
        except Exception:
            md_str = "# Analysis Report\n\n```json\n" + json_str + "\n```"

        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.download_button(
                label="💾 Download Analysis JSON",
                data=json_str,
                file_name=f"requirement_analysis_{result.get('document_source', 'report')}.json",
                mime="application/json",
                use_container_width=True,
            )
        with col_d2:
            st.download_button(
                label="📄 Download Markdown Report",
                data=md_str,
                file_name=f"requirement_analysis_{result.get('document_source', 'report')}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_d3:
            try:
                from app.tools.pdf_generator import generate_pdf_report
                pdf_target = pydantic_res if "pydantic_res" in locals() else result
                pdf_bytes = generate_pdf_report(pdf_target)
                st.download_button(
                    label="📄 Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"requirement_analysis_{result.get('document_source', 'report')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as pdf_err:
                st.error(f"⚠️ Unable to generate PDF report: {pdf_err}")

        st.divider()
        st.markdown("### 📄 Complete Markdown Report Preview")
        st.markdown(md_str)
