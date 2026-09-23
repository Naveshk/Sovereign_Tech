# Sovereign AI Workbench

> **A self-hosted, on-premise agentic AI workbench for confidential industrial knowledge work.**

Sovereign AI Workbench is a local AI platform designed for environments where sensitive documents, engineering data, internal reports, source code, and business information must remain within the organization's infrastructure.

The system combines **open-weight local models, multimodal document processing, RAG, tool-based agent execution, isolated code execution, deterministic engineering calculations, human approval workflows, artifact generation, and audit/provenance controls** into a single workbench.

The platform is designed around one principle:

> **Bring AI to the data — not the data to external AI services.**

---

## Problem

Industrial organizations such as refineries, PSUs, manufacturing units, and government organizations work with sensitive information including:

- Engineering reports
- Inspection documents
- P&IDs and technical drawings
- Internal SOPs and manuals
- Financial and operational documents
- Internal correspondence
- Source code and technical data
- Approval notes and management presentations

Sending this information to public cloud AI services may not be acceptable for confidential or regulated environments.

Sovereign AI Workbench addresses this requirement by keeping the AI workflow inside the organization's infrastructure.

---

## Solution

The workbench provides a local, modular AI environment capable of:

- Running open-weight models locally through Ollama
- Routing different tasks to different model capabilities
- Processing text, documents, images and scanned PDFs
- Searching organization-specific knowledge through local RAG
- Executing generated code inside an isolated Docker sandbox
- Performing deterministic engineering calculations
- Generating DOCX, PPTX, XLSX and PDF artifacts
- Requiring human approval before sensitive final artifacts
- Maintaining audit and provenance information
- Applying local authentication and role-based access control

---

## Architecture

```text
                         User
                          │
                          ▼
                  React / Vite UI
                          │
                    HTTP / SSE
                          │
                          ▼
                    FastAPI API
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
   Task Analyzer     Model Router      Context Manager
          │               │                │
          │               ▼                ▼
          │        Local Model Registry   Local RAG
          │               │                │
          │       ┌───────┼────────┐       ▼
          │       ▼       ▼        ▼    ChromaDB
          │     Qwen3   Coder      VL
          │                         │
          │                         ▼
          │                    OCR / Vision
          │
          ▼
                     Agent / Tool Layer
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
   File Tools       Engineering Engine   Code Sandbox
       │                  │                  │
       ▼                  ▼                  ▼
 PDF/DOCX/PPTX       Deterministic       Docker
 XLSX/CSV/Image      Calculations         isolated
       │
       └──────────────────┬──────────────────┘
                          ▼
                   Artifact Generation
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
           DOCX         XLSX         PPTX/PDF
                          │
                          ▼+
                    Human Review
                     │         │
                  Reject     Approve
                     │         │
                     ▼         ▼
                  Revision   Final Artifact
                                │
                         Hash / Provenance
                                │
                              Audit
```

---

## Core Capabilities

### Local Open-Weight Models

The workbench currently supports local Qwen-based models through Ollama:

| Model                | Primary Use                             |
| -------------------- | --------------------------------------- |
| Qwen3 8B             | General reasoning and synthesis         |
| Qwen2.5-Coder 7B     | Coding tasks                            |
| Qwen2.5-VL 7B        | Image and visual document understanding |
| Qwen3-Embedding 0.6B | Local semantic retrieval                |

Models are accessed through a modular model registry and routing layer rather than coupling the application directly to a single model.

---

## Modular Model Routing

The system separates **task understanding, model selection and model execution**.

```text
User Task
   │
   ▼
Task Analyzer
   │
   ▼
Required Operation / Capability
   │
   ▼
Model Router
   │
   ▼
Local Model Registry
   │
   ├── General
   ├── Coding
   ├── Vision
   ├── File Generation
   └── Synthesis
   │
   ▼
Ollama
   │
   ▼
Selected Local Model
```

This makes the architecture extensible when additional open-weight models are introduced.

---

## Agentic Workflow

The workbench is designed around multi-step execution instead of single-turn question answering.

A typical document workflow can be:

```text
User Request
     ↓
Task Analysis
     ↓
Execution Planning
     ↓
File Extraction
     ↓
OCR / Vision
     ↓
Local Knowledge Retrieval
     ↓
Reasoning / Calculation
     ↓
Artifact Generation
     ↓
Validation
     ↓
Human Review
     ↓
Final Artifact
```

The system can combine local tools and models during a single task.

---

## Multimodal Document Processing

The platform supports local processing of:

- PDF
- Scanned PDF
- DOCX
- PPTX
- XLSX / XLS
- CSV
- Images
- Text and Markdown documents

For scanned documents, the pipeline can use:

```text
Document
   ↓
Text Extraction
   ↓
OCR when required
   ↓
Local Vision Model when required
   ↓
Structured / Grounded Analysis
```

OCR and model assets should be pre-staged before deploying the system into a fully disconnected environment.

---

## Local RAG

Organization-specific knowledge can be indexed into a local vector database.

```text
Internal Document
      ↓
Chunking
      ↓
Local Embedding Model
      ↓
ChromaDB
      ↓
Semantic Retrieval
      ↓
Relevant Context
      ↓
Local LLM
```

This allows the assistant to ground responses in internal manuals, SOPs and other approved local documents without requiring an external knowledge service.

---

## Engineering Calculations

Important numerical calculations are handled through deterministic local tools rather than relying entirely on free-form LLM arithmetic.

The calculation workflow is:

```text
User / Document
      ↓
Input Extraction
      ↓
Validated Parameters
      ↓
Deterministic Calculation Engine
      ↓
Formula + Result + Assumptions
      ↓
Explanation / Report
```

This separation helps keep calculation logic reproducible and inspectable.

---

## Secure Code Execution

Generated code can be executed inside a Docker-based sandbox.

The sandbox is designed to apply controls such as:

- No network access
- Non-root execution
- CPU limits
- Memory limits
- PID limits
- Execution timeout
- Dropped Linux capabilities
- Read-only filesystem where applicable
- Temporary workspace

The purpose is to prevent generated code from directly executing with unrestricted access to the host environment.

---

## Human-in-the-Loop Approval

Sensitive artifacts are not treated as automatically approved outputs.

The workflow supports:

```text
AI Draft
   ↓
Human Review
   ├── Reject → Feedback → New Revision
   │
   └── Approve → Final Artifact
```

This is particularly useful for approval notes, technical reports and other documents where a responsible human should remain in the decision loop.

---

## Artifact Generation

The workbench can generate real files rather than returning only chat responses.

Supported artifact types include:

- DOCX
- XLSX
- PPTX
- PDF
- Source code

Generated artifacts can be validated and associated with provenance information.

---

## Security and Sovereignty

The architecture includes multiple security layers:

```text
Application-level policies
        +
Local model execution
        +
Docker isolation
        +
Host firewall controls
        +
Network monitoring
        +
Audit logging
        +
RBAC
        +
Artifact provenance
```

The system is designed for local deployment. A true air-gapped deployment requires the organization to isolate the host/server from external networks and pre-stage all required model and runtime assets.

**Important:** Application-level network blocking alone should not be treated as proof of a physical air gap.

---

## Authentication and RBAC

The backend includes local authentication and role-based access control.

Access can be separated by application roles and used together with protected knowledge and review workflows.

The current prototype uses local SQLite-based authentication and metadata storage.

---

## Audit and Provenance

The system maintains audit and artifact provenance information for important workflow actions.

Artifact integrity can be checked using SHA-256 hashes.

The distinction is intentional:

```text
AES-256-GCM
    → Confidentiality / encryption

SHA-256
    → Integrity verification

Audit Ledger
    → Traceability of system actions
```

---

## API Surface

Selected backend endpoints include:

```text
GET  /api/health

POST /api/chat
POST /api/chat/stream

GET  /api/files/{filename}

POST /api/knowledge/upload
GET  /api/knowledge/status

POST /api/auth/signup
POST /api/auth/login
GET  /api/auth/roles

GET  /api/admin/files
GET  /api/admin/audit

POST /api/sandbox/execute

GET  /api/network/status
```

The streaming chat endpoint provides progress events while long-running local model and tool operations are executing.

---

## Technology Stack

### Frontend

- React
- Vite
- JavaScript
- SSE / HTTP

### Backend

- Python
- FastAPI
- Uvicorn

### AI / ML

- Ollama
- Qwen3
- Qwen2.5-Coder
- Qwen2.5-VL
- Qwen3-Embedding
- PaddleOCR

### Knowledge Retrieval

- ChromaDB
- Local embeddings
- RAG pipeline

### Document Processing

- PyMuPDF
- python-docx
- python-pptx
- openpyxl
- pandas
- ReportLab

### Security / Isolation

- Docker
- SQLite
- AES-256-GCM
- SHA-256
- RBAC
- Local firewall controls
- tcpdump/network monitoring

---

## Project Structure

```text
.
├── app/                    # FastAPI backend and services
├── frontend/               # React/Vite frontend
├── sandbox/                # Docker sandbox configuration
├── docker/                 # Container configuration
├── security/               # Firewall and network monitoring
├── tests/                  # Automated tests
├── requirements.txt        # Python dependencies
├── requirements-ocr.txt    # OCR dependencies
├── README.md
├── SECURITY.md
└── ARCHITECTURE.md
```

---

## Local Development

### 1. Create Python environment

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
```

### 2. Install backend dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-ocr.txt
```

### 3. Prepare Ollama

Install Ollama and make sure the required local models are available:

```powershell
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5vl:7b
ollama pull qwen3-embedding:0.6b
```

Verify:

```powershell
ollama list
```

### 4. Start the backend

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### 5. Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

If required, configure:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

---

## Testing

Run the backend test suite with:

```powershell
python -m unittest discover -s tests -v
```

or:

```powershell
python -m pytest -q
```

The test suite covers areas including:

- Model routing
- File processing
- RAG access
- Engineering calculations
- Artifact generation
- Provenance
- Audit
- Encryption
- Network security
- Sandbox hardening
- Human review
- Resilience
- End-to-end workflows

---

## Example Industrial Workflow

Example:

> Analyze a scanned inspection report and prepare an approval-ready technical note.

The workbench can process the task as:

```text
Scanned Inspection Report
        ↓
PDF extraction / OCR
        ↓
Vision processing when required
        ↓
Local knowledge retrieval
        ↓
Engineering calculation when required
        ↓
Local reasoning
        ↓
Draft approval note
        ↓
Human review
        ↓
Revision if rejected
        ↓
Final DOCX
        ↓
Integrity / provenance record
        ↓
Audit entry
```

No external cloud AI provider is required by the core architecture.

---

## Security Considerations

This repository contains application and deployment configuration, not production secrets.

Runtime data such as:

- Local database files
- Encryption keys
- Uploaded documents
- Generated artifacts
- Model files
- Caches

should be maintained outside source control.

For a production air-gapped environment:

1. Pre-stage all required models and runtime assets.
2. Disable or remove unnecessary external network paths.
3. Apply host firewall policy.
4. Run sandboxed workloads with restricted privileges.
5. Monitor network activity.
6. Protect encryption keys separately from application source.
7. Integrate enterprise authentication where required.
8. Validate the deployment in the organization's security environment.

---

## Current Status

This repository represents a **working prototype / research implementation** of a sovereign, on-premise agentic AI workbench.

The architecture is designed to be extensible toward production deployment, but production adoption requires environment-specific security validation, enterprise identity integration, model benchmarking, hardware sizing, and operational hardening.

---

## Design Principles

The project follows several core principles:

- **Local-first:** sensitive workloads stay within the organization's infrastructure.
- **Model-agnostic:** the workbench is not tied to a single LLM.
- **Tool-driven:** agents can use local tools instead of producing only text.
- **Deterministic where possible:** calculations and artifact generation use controlled software components.
- **Human-in-the-loop:** sensitive outputs can require explicit review.
- **Auditable:** important actions and artifacts are traceable.
- **Extensible:** new models and tools can be introduced without redesigning the entire system.

---

## License

Add the project's chosen open-source license here before publishing the repository.

For example:

```text
MIT License
```

Only use a license that matches the project's actual intended distribution terms.

---

## Acknowledgement

Built as a prototype exploring practical deployment of open-weight multimodal AI for confidential, on-premise industrial workflows.
