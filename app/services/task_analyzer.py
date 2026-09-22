from pathlib import Path


def analyze_task(message: str, file_path: str | None = None, file_type: str | None = None) -> dict:
    text = (message or "").lower()
    ext = Path(file_path).suffix.lower() if file_path else ""

    requires_engineering_calculation = any(w in text for w in [
        "barlow", "hoop stress", "pressure capacity", "pipe pressure",
        "remaining life", "remaining thickness", "corrosion rate",
    ])

    requires_coding = any(w in text for w in [
        "code", "coding", "program", "python", "javascript", "java", "debug",
        "function", "script", "algorithm"
    ])
    explicit_rag = any(w in text for w in [
        "sop", "manual", "policy", "knowledge base", "knowledgebase",
        "procedure", "guideline", "regulation", "company format",
        "according to our", "according to the company", "according to our documents",
        "internal document", "internal documents", "company document", "company documents",
        "uploaded knowledge", "knowledge document", "knowledge documents"
    ])

    excel_file = ext in {".xlsx", ".xls", ".csv"}
    pdf_file = ext == ".pdf"
    docx_file = ext == ".docx"
    pptx_file = ext == ".pptx"
    text_file = ext in {".txt", ".md"}

    # When a supported file is attached, content questions should analyze the file
    # even if the user does not literally say "analyze" (for example,
    # "give the unit names in this DOCX" or "what is in this PDF").
    attached_content_file = bool(file_path) and ext in {
        ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv", ".txt", ".md"
    }

    wants_excel = any(w in text for w in ["excel", "xlsx", "spreadsheet", "workbook"]) and any(
        w in text for w in ["generate", "create", "make", "export", "prepare", "save"]
    )
    wants_pdf = any(w in text for w in ["pdf", "report pdf", "pdf report"]) and any(
        w in text for w in ["generate", "create", "make", "export", "prepare", "save"]
    )
    wants_docx = any(w in text for w in [
        "docx", "word", "word document", "document", "doc file",
        "permission letter", "approval note"
    ]) and any(
        w in text for w in ["generate", "create", "make", "prepare", "write", "build", "produce"]
    )
    wants_pptx = any(w in text for w in ["ppt", "pptx", "powerpoint", "presentation", "slides"]) and any(
        w in text for w in ["generate", "create", "make", "export", "prepare", "build"]
    )

    requires_file_generation = wants_excel or wants_pdf or wants_docx or wants_pptx or any(
        w in text for w in ["generate document", "generate report"]
    )

    analyze_excel = excel_file and (
        attached_content_file or requires_file_generation or any(w in text for w in [
            "analyze", "analyse", "summary", "summarize", "top ", "find",
            "calculate", "compare", "inspect"
        ])
    )
    analyze_pdf = pdf_file and (
        attached_content_file or requires_file_generation or any(w in text for w in [
            "analyze", "analyse", "summarize", "summary", "extract", "inspect",
            "find", "review"
        ])
    )
    analyze_docx = docx_file and (
        attached_content_file or requires_file_generation or any(w in text for w in [
            "analyze", "analyse", "summarize", "summary", "extract", "inspect",
            "review", "read", "understand"
        ])
    )
    analyze_pptx = pptx_file and (
        attached_content_file or requires_file_generation or any(w in text for w in [
            "analyze", "analyse", "summarize", "summary", "extract", "inspect",
            "review", "read", "understand"
        ])
    )
    analyze_text_file = text_file and (
        attached_content_file or requires_file_generation or any(w in text for w in [
            "analyze", "analyse", "summarize", "summary", "extract", "inspect",
            "review", "read", "understand"
        ])
    )

    requires_vision = any(w in text for w in [
        "image", "photo", "picture", "scanned", "scan", "drawing",
        "handwritten", "p&id", "diagram"
    ])
    if pdf_file and any(w in text for w in [
        "scanned", "scan", "handwritten", "drawing", "diagram", "p&id"
    ]):
        requires_vision = True
    if file_type == "image":
        requires_vision = True

    output_type = (
        "xlsx" if wants_excel else
        "pdf" if wants_pdf else
        "pptx" if wants_pptx else
        "docx" if wants_docx else None
    )

    knowledge_query = any(w in text for w in [
        "what does our", "what is our", "tell me about our", "according to",
        "based on our", "from our documents", "from the knowledge base",
        "from our knowledge", "in our documents", "in the uploaded documents",
        "company policy", "company procedure", "internal policy", "internal procedure",
        "search our knowledge", "search the knowledge base", "find in our documents",
        "find in the knowledge base", "is there anything in our documents", "do our documents say"
    ])
    requires_rag = explicit_rag or knowledge_query or any(w in text for w in [
        "using our template", "use our template", "company style", "company format"
    ])

    if analyze_excel and requires_file_generation:
        task_type = "excel"
    elif analyze_pdf and requires_file_generation:
        task_type = "pdf"
    elif analyze_pptx and requires_file_generation:
        task_type = "pptx"
    elif analyze_docx and requires_file_generation:
        task_type = "document"
    elif analyze_excel:
        task_type = "excel_analysis"
    elif analyze_pdf:
        task_type = "pdf_analysis"
    elif analyze_pptx:
        task_type = "pptx_analysis"
    elif analyze_docx or analyze_text_file:
        task_type = "document_analysis"
    elif requires_coding and requires_vision:
        task_type = "multimodal_coding"
    elif requires_vision:
        task_type = "multimodal"
    elif requires_coding:
        task_type = "coding"
    elif requires_file_generation:
        task_type = "file_generation"
    elif requires_rag:
        task_type = "knowledge"
    else:
        task_type = "general"

    return {
        "task_type": task_type,
        "requires_vision": requires_vision,
        "requires_engineering_calculation": requires_engineering_calculation,
        "requires_coding": requires_coding,
        "requires_rag": requires_rag,
        "requires_file_generation": requires_file_generation,
        "analyze_excel": analyze_excel,
        "analyze_pdf": analyze_pdf,
        "analyze_docx": analyze_docx,
        "analyze_pptx": analyze_pptx,
        "analyze_text_file": analyze_text_file,
        "output_type": output_type,
        "file_attached": bool(file_path),
        "file_type": file_type,
    }
