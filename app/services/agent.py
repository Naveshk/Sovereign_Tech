import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from app.services.model_router import route_model
from app.services.observability import timed
from app.services.ollama_client import generate_response as _ollama_generate_response
from app.services.resilience import resilient_generate_response, blind_resample
from app.services.vision_service import analyze_industrial_image
from app.services.file_generator import create_document_title
from app.services.rag.pipeline import run_rag
from app.services.file_tools.pdf_tools import analyze_pdf
from app.services.file_tools.excel_tools import (
    inspect_excel,
    dataframe_to_records,
    markdown_table_to_records,
    generate_excel_from_records,
)
from app.services.file_tools.document_tools import analyze_docx
from app.services.file_tools.ppt_tools import analyze_pptx, generate_pptx
from app.services.file_tools.document_generators import markdown_to_pdf
from app.services.file_tools.validation_tools import validate_generated_file

BASE_DIR = Path(__file__).resolve().parents[2]


def generate_response(model: str, prompt: str) -> str:
    """Batch 29 compatibility wrapper: bounded retry + timeout + circuit protection."""
    timeout = float(os.getenv("SWB_MODEL_TIMEOUT_SECONDS", "60"))
    return resilient_generate_response(
        model,
        prompt,
        max_attempts=3,
        timeout_seconds=max(1.0, min(timeout, 300.0)),
    )


def _blind_draft(model: str, prompt: str) -> dict[str, Any]:
    samples = max(1, min(int(os.getenv("SWB_BLIND_RESAMPLES", "2")), 3))
    return blind_resample(model, prompt, samples=samples)

GENERATED_DIR = BASE_DIR / "data" / "generated"
from app.services.sandbox.manager import sandbox_manager
from app.services.draft_manager import create_draft
from app.services.engineering_engine import (
    EngineeringInputError,
    barlow_pipe_pressure,
    remaining_life,
)


def _file_result(generated: dict) -> dict:
    return {**generated, "download_url": f"/api/files/{generated['filename']}"}


def _extract_structured_records(evidence: str, message: str, model_name: str) -> tuple[list[dict], str]:
    """Convert source evidence into dynamic rows for Excel without hard-coded columns."""
    records = markdown_table_to_records(evidence)
    if records:
        return records, "markdown_table"

    prompt = f"""You are a structured data extraction engine.

Convert ONLY the supplied evidence into rows suitable for an Excel workbook.

USER REQUEST:
{message}

SOURCE EVIDENCE:
{evidence[:30000]}

Rules:
- Use only values present in the evidence.
- Do not invent, estimate, or infer missing values.
- Detect column names dynamically from the source.
- Preserve all available rows and values.
- Use null for unreadable/unavailable values.
- Return ONLY valid JSON, no Markdown or explanation.

Required shape:
{{"records":[{{"detected_column":"value"}}]}}
"""
    response = generate_response(model_name, prompt)
    match = re.search(r"\{[\s\S]*\}", response)
    if not match:
        raise ValueError("Structured extraction returned no JSON object.")
    data = json.loads(match.group(0))
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError("Structured extraction JSON has no records list.")
    records = [r for r in records if isinstance(r, dict)]
    if not records:
        raise ValueError("No structured rows were extracted.")
    return records, "llm_structured_json"


def _generate_excel_from_source(
    title: str,
    message: str,
    file_path: str | None,
    evidence: str,
    model_name: str,
) -> tuple[dict, str, int]:
    """Prefer exact source rows for spreadsheets; use local LLM only for unstructured sources."""
    records: list[dict[str, Any]]
    method: str

    if file_path and Path(file_path).suffix.lower() in {".xlsx", ".xls", ".csv"}:
        records = dataframe_to_records(file_path)
        method = "source_workbook_rows"
    else:
        records, method = _extract_structured_records(evidence, message, model_name)

    if not records:
        raise ValueError("No data rows available for Excel generation.")

    output_path = GENERATED_DIR / f"generated_{uuid.uuid4().hex[:10]}.xlsx"
    generated = generate_excel_from_records(
        output_path=str(output_path),
        records=records,
        sheet_name="Data",
        title=title,
        summary={
            "Source": Path(file_path).name if file_path else "Local evidence / knowledge context",
            "Extraction method": method,
            "Records": len(records),
        },
    )
    validate_generated_file(generated["file_path"], "xlsx")
    return generated, method, len(records)



def _engineering_calculation_from_message(message: str) -> dict[str, Any] | None:
    """Run supported deterministic calculations when all named inputs are present.

    Chat integration is intentionally conservative: missing/ambiguous inputs produce
    no arithmetic rather than an LLM guess. The dedicated API exposes the same engine.
    """
    text = (message or "").lower()

    def number(name: str) -> float | None:
        match = re.search(
            rf"(?:{re.escape(name)})\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            text,
        )
        return float(match.group(1)) if match else None

    if "barlow" in text or "hoop stress" in text or "pressure capacity" in text:
        values = {
            "pressure_mpa": number("pressure_mpa"),
            "diameter_mm": number("diameter_mm"),
            "thickness_mm": number("thickness_mm"),
            "allowable_stress_mpa": number("allowable_stress_mpa"),
        }
        if all(v is not None for v in values.values()):
            return barlow_pipe_pressure(**values)

    if "remaining life" in text or "corrosion rate" in text or "remaining thickness" in text:
        values = {
            "current_thickness_mm": number("current_thickness_mm"),
            "minimum_required_thickness_mm": number("minimum_required_thickness_mm"),
            "corrosion_rate_mm_per_year": number("corrosion_rate_mm_per_year"),
        }
        if all(v is not None for v in values.values()):
            return remaining_life(**values)

    return None

def _run_agent_impl(message: str, task_analysis: dict, file_path: str | None = None, employee_id: str | None = None, role: str | None = None, department: str | None = None, conversation_context: str | None = None, is_follow_up: bool = False) -> dict:
    results, context_parts = [], []
    if conversation_context:
        context_parts.append(
            "RECENT CONVERSATION CONTEXT (supporting context only; the current user request is authoritative):\n"
            + conversation_context[:12000]
        )

    if task_analysis.get("requires_engineering_calculation"):
        try:
            calculation = _engineering_calculation_from_message(message)
            if calculation is None:
                results.append({
                    "step": len(results)+1,
                    "operation": "engineering_calculation",
                    "model": "deterministic engineering engine",
                    "status": "needs_input",
                    "response": (
                        "Engineering calculation detected, but required named inputs "
                        "are missing. No values were guessed. Use the documented input names."
                    ),
                })
            else:
                encoded = json.dumps(calculation, ensure_ascii=False, indent=2)
                results.append({
                    "step": len(results)+1,
                    "operation": "engineering_calculation",
                    "model": "deterministic engineering engine",
                    "response": encoded,
                    "calculation": calculation["calculation"],
                    "warnings": calculation.get("warnings", []),
                })
                context_parts.append("DETERMINISTIC ENGINEERING RESULT:\n" + encoded)
        except EngineeringInputError as exc:
            results.append({
                "step": len(results)+1,
                "operation": "engineering_calculation",
                "model": "deterministic engineering engine",
                "status": "validation_error",
                "response": f"Input validation failed: {exc}",
            })

    if task_analysis.get("requires_vision"):
        if not file_path:
            return {"status": "error", "response": "Vision task requires a file."}
        model = route_model(task_analysis, "vision")
        vision_result = analyze_industrial_image(
            file_path,
            message or "Analyze this industrial image.",
            force_vision=bool(task_analysis.get("requires_vision")),
        )
        response = json.dumps(vision_result, ensure_ascii=False, indent=2)
        results.append({
            "step": len(results)+1,
            "operation": "vision",
            "model": model["model_name"],
            "response": response,
            "extraction": vision_result["engineering_extraction"],
        })
        context_parts.append("VISION RESULT:\n" + response)

    if task_analysis.get("analyze_pdf") and file_path:
        pdf = analyze_pdf(file_path)
        response = pdf["text"]
        results.append({"step": len(results)+1, "operation": "pdf_analysis", "model": "PyMuPDF / local OCR / vision fallback", "response": response, "mode": pdf["mode"]})
        context_parts.append("PDF ANALYSIS:\n" + response[:16000])

    if task_analysis.get("analyze_excel") and file_path:
        excel = inspect_excel(file_path)
        encoded = json.dumps(excel, ensure_ascii=False, indent=2)
        results.append({"step": len(results)+1, "operation": "excel_analysis", "model": "pandas / openpyxl", "response": encoded})
        context_parts.append("EXCEL ANALYSIS:\n" + encoded[:20000])

    if task_analysis.get("analyze_docx") and file_path:
        docx = analyze_docx(file_path)
        encoded = json.dumps(docx, ensure_ascii=False, indent=2)
        results.append({"step": len(results)+1, "operation": "docx_analysis", "model": "python-docx", "response": encoded})
        context_parts.append("DOCX ANALYSIS:\n" + encoded[:20000])

    if task_analysis.get("analyze_pptx") and file_path:
        ppt = analyze_pptx(file_path)
        encoded = json.dumps(ppt, ensure_ascii=False, indent=2)
        results.append({"step": len(results)+1, "operation": "pptx_analysis", "model": "python-pptx", "response": encoded})
        context_parts.append("PPTX ANALYSIS:\n" + encoded[:20000])

    if task_analysis.get("analyze_text_file") and file_path:
        p = Path(file_path)
        text = p.read_text(encoding="utf-8", errors="replace")
        results.append({"step": len(results)+1, "operation": "document_analysis", "model": "local text parser", "response": text[:20000]})
        context_parts.append("DOCUMENT TEXT:\n" + text[:20000])

    if task_analysis.get("requires_rag"):
        try:
            rag = run_rag(message, top_k=5, role=role, department=department)
            rag_summary = rag["context"] if rag["found"] else "No relevant local knowledge-base chunks were found."
            results.append({
                "step": len(results)+1,
                "operation": "rag",
                "model": "Qwen3-Embedding-0.6B + ChromaDB",
                "response": rag_summary,
                "sources": [x["metadata"] for x in rag["results"]],
                "evidence": rag.get("evidence", []),
                "access": rag.get("access", {}),
                "found": rag["found"],
            })
            context_parts.append("KNOWLEDGE BASE CONTEXT:\n" + rag_summary)
        except Exception as exc:
            print(f"[rag_error] {type(exc).__name__}: {exc}")
            results.append({
                "step": len(results)+1,
                "operation": "rag",
                "model": "Qwen3-Embedding-0.6B + ChromaDB",
                "status": "error",
                "response": "Local knowledge retrieval is currently unavailable."
            })
            context_parts.append("KNOWLEDGE BASE CONTEXT:\nNo local knowledge was retrieved.")

    context = "\n\n".join(context_parts)

    if task_analysis.get("requires_coding"):
        model = route_model(task_analysis, "coding")
        prompt = f"USER REQUEST:\n{message}\n\nPREVIOUS RESULTS:\n{context}\n\nPerform the coding task. Return complete runnable Python code inside one ```python``` block followed by a concise explanation."
        response = generate_response(model["ollama_model"], prompt)
        code_match = re.search(r"```(?:python|py)?\s*\n([\s\S]*?)```", response, re.IGNORECASE)
        code = code_match.group(1).strip() if code_match else response.strip()
        sandbox_result = sandbox_manager.execute(code=code, language="python", timeout=10)
        results.append({"step": len(results)+1, "operation": "coding", "model": model["model_name"], "response": response, "sandbox": sandbox_result})

        if sandbox_result.get("status") in {"failed", "timeout"}:
            repair_prompt = f"USER REQUEST:\n{message}\n\nPREVIOUS CODE:\n{code}\n\nSANDBOX ERROR:\n{sandbox_result.get('stderr','')}\n\nFix the code. Return only one complete Python code block."
            repaired = generate_response(model["ollama_model"], repair_prompt)
            repaired_match = re.search(r"```(?:python|py)?\s*\n([\s\S]*?)```", repaired, re.IGNORECASE)
            repaired_code = repaired_match.group(1).strip() if repaired_match else repaired.strip()
            retry_result = sandbox_manager.execute(code=repaired_code, language="python", timeout=10)
            results.append({"step": len(results)+1, "operation": "sandbox_retry", "model": model["model_name"], "response": repaired, "sandbox": retry_result})
            sandbox_result, response = retry_result, repaired

        context += "\nCODING RESULT:\n" + response
        context += "\nSANDBOX RESULT:\n" + json.dumps(sandbox_result, ensure_ascii=False)

    # Produce a grounded answer before document generation.
    # For follow-up turns, the recent conversation is part of the actual prompt.
    # This is critical for requests such as "What is an agent?" -> "Give in simple words."
    has_evidence_task = (
        task_analysis.get("analyze_pdf") or task_analysis.get("analyze_excel") or
        task_analysis.get("analyze_docx") or task_analysis.get("analyze_pptx") or
        task_analysis.get("analyze_text_file") or task_analysis.get("requires_rag") or
        task_analysis.get("requires_vision")
    )
    if (
        (context and has_evidence_task) or
        (is_follow_up and conversation_context and not task_analysis.get("requires_coding"))
    ) and not task_analysis.get("requires_coding"):
        model = route_model(task_analysis, "general")
        if is_follow_up and conversation_context and not has_evidence_task:
            synthesis_prompt = f"""You are continuing an existing local chat.

RECENT CONVERSATION:
{conversation_context[:12000]}

CURRENT USER REQUEST:
{message}

Instructions:
- Treat the current request as an instruction about the relevant previous topic.
- Resolve references such as "it", "that", "this", "above", or "give in simple words" from the recent conversation.
- Keep the original topic and important facts from the previous answer.
- Apply the user's new instruction to that topic.
- Do not answer as if the current message were a brand-new topic.
- Do not mention that you used conversation context.
- Give a clear, natural answer."""
        else:
            synthesis_prompt = f"""Answer the user's request using only the evidence below.
If evidence is insufficient, say so. Do not invent facts.

USER REQUEST:
{message}

EVIDENCE:
{context[:24000]}

Give a clear, useful answer. Mention important source names when available."""
        synthesis = generate_response(model["ollama_model"], synthesis_prompt)
        results.append({"step": len(results)+1, "operation": "reasoning", "model": model["model_name"], "response": synthesis})
        context += "\nFINAL REASONING:\n" + synthesis

    if task_analysis.get("requires_file_generation"):
        output = task_analysis.get("output_type") or "docx"
        title = create_document_title(message)

        try:
            # Batch 13: every deliverable becomes Draft v1 first.  The existing
            # artifact generators are intentionally not called here; Batch 15
            # will add the approval-gated final generation step.
            if output == "xlsx":
                general_model = route_model(task_analysis, "general")
                if file_path and Path(file_path).suffix.lower() in {".xlsx", ".xls", ".csv"}:
                    records = dataframe_to_records(file_path)
                    extraction_method = "source_workbook_rows"
                else:
                    records, extraction_method = _extract_structured_records(
                        context, message, general_model["ollama_model"]
                    )
                if not records:
                    raise ValueError("No data rows available for Excel draft.")
                draft_content = json.dumps(records, ensure_ascii=False, indent=2, default=str)
                draft_bundle = create_draft(
                    requester_employee_id=employee_id,
                    requester_username=None,
                    requester_role=role,
                    action="deliverable_review",
                    title=title,
                    artifact_type="xlsx",
                    content=draft_content,
                    source_path=file_path,
                    metadata={"extraction_method": extraction_method, "records_count": len(records), "original_request": message},
                )
                results.append({
                    "step": len(results)+1,
                    "operation": "draft_generation",
                    "model": "openpyxl / local extraction",
                    "draft": draft_bundle["draft"],
                    "human_review": draft_bundle["review"],
                    "requires_human_review": True,
                    "requires_final_artifact": True,
                    "response": f"Draft v1 prepared for Excel with {len(records)} structured data rows. Final artifact not generated yet.",
                })

            elif output == "pdf":
                model = route_model(task_analysis, "file_generation")
                prompt = f"""Create draft PDF-ready content for the user's request.
Use only supplied source facts. Do not invent information.
USER REQUEST:
{message}
SOURCE/KNOWLEDGE CONTEXT:
{context}
Return structured Markdown with headings, bullets and tables where useful."""
                resample = _blind_draft(model["ollama_model"], prompt)
                generated_content = resample["content"]
                draft_bundle = create_draft(
                    requester_employee_id=employee_id,
                    requester_username=None,
                    requester_role=role,
                    action="deliverable_review",
                    title=title,
                    artifact_type="pdf",
                    content=generated_content,
                    source_path=file_path,
                    metadata={"original_request": message},
                )
                results.append({
                    "step": len(results)+1,
                    "operation": "draft_generation",
                    "model": model["model_name"],
                    "draft": draft_bundle["draft"],
                    "human_review": draft_bundle["review"],
                    "requires_human_review": True,
                    "requires_final_artifact": True,
                    "response": generated_content,
                    "resampling": resample,
                })

            elif output == "pptx":
                model = route_model(task_analysis, "file_generation")
                prompt = f"""Create concise draft presentation content for the user's request.
Use ONLY supplied source facts. Do not invent information.
USER REQUEST:
{message}
SOURCE/KNOWLEDGE CONTEXT:
{context}
Return Markdown. Use # for slide titles and - for slide bullets. Create only relevant slides."""
                resample = _blind_draft(model["ollama_model"], prompt)
                generated_content = resample["content"]
                draft_bundle = create_draft(
                    requester_employee_id=employee_id,
                    requester_username=None,
                    requester_role=role,
                    action="deliverable_review",
                    title=title,
                    artifact_type="pptx",
                    content=generated_content,
                    source_path=file_path,
                    metadata={"original_request": message},
                )
                results.append({
                    "step": len(results)+1,
                    "operation": "draft_generation",
                    "model": model["model_name"],
                    "draft": draft_bundle["draft"],
                    "human_review": draft_bundle["review"],
                    "requires_human_review": True,
                    "requires_final_artifact": True,
                    "response": generated_content,
                    "resampling": resample,
                })

            else:
                model = route_model(task_analysis, "file_generation")
                prompt = f"""Create a draft for the user's requested deliverable.

USER REQUEST:
{message}

SOURCE/KNOWLEDGE CONTEXT:
{context}

Rules:
- Use only supplied source facts for factual claims.
- Do not invent company policy or missing values.
- Produce professional, structured content.
- Use headings, lists and tables where appropriate.
- Return only the draft content, without meta commentary."""
                resample = _blind_draft(model["ollama_model"], prompt)
                generated_content = resample["content"]
                evidence_refs = []
                for item in results:
                    if item.get("operation") == "rag":
                        evidence_refs.extend(item.get("evidence", []) or [])
                action = "approval_note_review" if any(
                    token in message.lower() for token in ("approval note", "approval request", "approval document")
                ) else "deliverable_review"
                draft_bundle = create_draft(
                    requester_employee_id=employee_id,
                    requester_username=None,
                    requester_role=role,
                    action=action,
                    title=title,
                    artifact_type="docx",
                    content=generated_content,
                    source_path=file_path,
                    metadata={"evidence_refs": evidence_refs, "original_request": message},
                )
                results.append({
                    "step": len(results)+1,
                    "operation": "draft_generation",
                    "model": model["model_name"],
                    "draft": draft_bundle["draft"],
                    "human_review": draft_bundle["review"],
                    "requires_human_review": True,
                    "requires_final_artifact": True,
                    "response": generated_content,
                    "resampling": resample,
                })

            context += f"\nDRAFT V1: {title} ({output}) — final artifact not generated yet."

        except PermissionError as exc:
            results.append({
                "step": len(results)+1,
                "operation": "draft_generation",
                "status": "review_authorization_error",
                "error_type": "HUMAN_REVIEW_AUTHORIZATION_ERROR",
                "response": str(exc),
            })
        except Exception as exc:
            print(f"[draft_generation_error] {type(exc).__name__}: {exc}")
            results.append({
                "step": len(results)+1,
                "operation": "draft_generation",
                "status": "error",
                "error_type": "DRAFT_GENERATION_ERROR",
                "response": "Draft generation failed. The requested final artifact was not generated.",
            })

    if not results:
        model = route_model(task_analysis, "general")
        response = generate_response(model["ollama_model"], message)
        results.append({"step": 1, "operation": "general", "model": model["model_name"], "response": response})

    final_response = next(
        (x["response"] for x in reversed(results)
         if x.get("response") and x.get("operation") not in {
             "vision", "pdf_analysis", "excel_analysis", "docx_analysis",
             "pptx_analysis", "document_analysis", "rag", "file_generation"
         }),
        None
    )

    if task_analysis.get("requires_coding"):
        sandbox_items = [x.get("sandbox") for x in results if x.get("sandbox")]
        if sandbox_items:
            last_sandbox = sandbox_items[-1]
            verification = (
                f"\n\n**Sandbox verification:** {str(last_sandbox.get('status','unknown')).upper()} · "
                f"Network: {last_sandbox.get('network','disabled')} · "
                f"Exit code: {last_sandbox.get('exit_code','—')} · "
                f"Duration: {last_sandbox.get('duration',0)}s"
            )
            if last_sandbox.get("stdout"):
                verification += f"\n\nOutput:\n```text\n{last_sandbox['stdout']}\n```"
            if last_sandbox.get("stderr"):
                verification += f"\n\nErrors:\n```text\n{last_sandbox['stderr']}\n```"
            final_response = (final_response or "") + verification

    if not final_response:
        generated = next((x for x in reversed(results) if x.get("download_url")), None)
        final_response = (
            f"Task completed successfully. Generated file: {generated.get('file', {}).get('filename', 'download')}"
            if generated
            else (results[-1].get("response") or context)
        )

    generated_files = [
        {
            "filename": x.get("file", {}).get("filename"),
            "title": x.get("file", {}).get("title") or x.get("file", {}).get("filename"),
            "download_url": x.get("download_url"),
            "file_type": x.get("file", {}).get("file_type"),
        }
        for x in results
        if x.get("download_url") and x.get("file", {}).get("filename")
    ]

    return {
        "message": message,
        "task_analysis": task_analysis,
        "results": results,
        "generated_files": generated_files,
        "final_context": context,
        "final_response": final_response,
        "status": "completed" if not any(x.get("status") == "error" for x in results) else "error",
        "conversation_context": {
            "used": bool(conversation_context),
            "is_follow_up": bool(is_follow_up),
        },
    }


def run_agent(
    message: str,
    task_analysis: dict,
    file_path: str | None = None,
    employee_id: str | None = None,
    role: str | None = None,
    department: str | None = None,
    conversation_context: str | None = None,
    is_follow_up: bool = False,
) -> dict:
    """Compatibility wrapper with bounded error handling and a local fallback."""
    with timed("workflow.agent", metadata={"operation": "run_agent"}):
        try:
            return _run_agent_impl(
                message, task_analysis, file_path, employee_id, role, department,
                conversation_context, is_follow_up
            )
        except Exception as exc:
            error_type = type(exc).__name__
            detail = str(exc)[:240]
            if "Timeout" in error_type or "timeout" in detail.lower():
                code = "LOCAL_MODEL_TIMEOUT"
                user_message = (
                    "The local model exceeded the configured time limit. "
                    "No final artifact was generated. Please retry the task."
                )
            elif "Circuit" in error_type:
                code = "LOCAL_MODEL_CIRCUIT_OPEN"
                user_message = (
                    "The selected local model is temporarily unavailable after repeated "
                    "failures. Please retry after the recovery window."
                )
            else:
                code = "WORKFLOW_EXECUTION_ERROR"
                user_message = (
                    "The local workflow could not complete safely. "
                    "No final artifact was generated. Please retry the task."
                )
            return {
                "message": message,
                "task_analysis": task_analysis,
                "results": [{
                    "step": 1,
                    "operation": "error_recovery",
                    "status": "error",
                    "error_type": code,
                    "response": user_message,
                }],
                "generated_files": [],
                "final_context": "",
                "final_response": user_message,
                "status": "error",
                "fallback": {
                    "used": True,
                    "strategy": "safe_local_response",
                    "error_code": code,
                    "detail": detail,
                },
                "conversation_context": {
                    "used": bool(conversation_context),
                    "is_follow_up": bool(is_follow_up),
                },
            }
