# PRD: Knowledge Base Feature

## 1. Overview
The Knowledge Base (KB) feature allows marketing teams to upload and manage project-specific documents (e.g., product manuals, brand guidelines, competitor analysis) to ground the AI chatbot's responses. This ensures that the AI provides accurate, evidence-based insights derived from official company knowledge rather than relying solely on general training data.

## 2. Target Users
- **Product Marketing Managers**: To ensure the AI understands product nuances.
- **PR/Communications Teams**: To provide the AI with brand-approved messaging and risk mitigation strategies.
- **Product Managers**: To feed technical specifications into the analysis loop.

## 3. Core Functionality

### 3.1 Knowledge Base Management
- **Project-Specific Isolation**: Knowledge bases are scoped to a `Monitor Profile` (Project).
- **Multiple Bases**: Users can create multiple knowledge bases per project (e.g., "Product Specs", "Brand Voice").
- **Activation Control**: Only one knowledge base can be "active" at a time for a given project, which determines the context used by the chatbot.

### 3.2 Data Ingestion
- **File Uploads**: Supports `.md`, `.txt`, `.csv`, and `.json` files (max 3MB).
- **URL Ingestion**: Supports fetching and cleaning text from public web pages.
- **Automated Processing**:
    - **Text Normalization**: Strips HTML/scripts, unescapes characters, and cleans whitespace.
    - **Chunking**: Automatically breaks long documents into manageable segments (~1200 characters) for efficient retrieval.
    - **Checksum Deduplication**: Prevents duplicate ingestion of the same file content within a base.

### 3.3 Knowledge Retrieval (RAG)
- **Semantic Context**: When a user chats with a video analysis, the system retrieves the most relevant chunks from the active knowledge base.
- **Keyword-Based Scoring**: Uses a lightweight token-overlap scoring mechanism with prefix bonuses to rank relevant knowledge.
- **Context Assembling**: Combines a high-level "Knowledge Summary" with specific "Retrieved Evidence" chunks into the AI's prompt context (capped at ~4000 characters).

### 3.4 Automated Summarization
- **Snapshot Generation**: Automatically generates a Markdown-formatted summary of the indexed sources for quick human review and LLM grounding.

## 4. Tech Stack

### 4.1 Backend
- **Framework**: FastAPI (Python 3.10+)
- **Database**: SQLite (via SQLAlchemy ORM)
- **Processing**: 
    - `hashlib` for content checksums.
    - `re` and `html` for text cleaning and normalization.
    - `urllib` for web content fetching.

### 4.2 Frontend
- **UI**: Vanilla JavaScript + HTML Templates (Server-rendered).
- **State Management**: Client-side `knowledge-settings.js` for managing the KB lifecycle and file uploads.

### 4.3 AI/LLM
- **Model**: Gemini (configured via `gemini-3-flash`).
- **Pattern**: Retrieval-Augmented Generation (RAG).

## 5. Data Model

- **`KnowledgeBase`**: Container for sources, scoped to a project.
- **`KnowledgeSource`**: Individual file or URL entry with status tracking (`QUEUED`, `PROCESSING`, `READY`, `FAILED`).
- **`KnowledgeChunk`**: Granular text segments used for retrieval.
- **`KnowledgeSnapshot`**: Cached Markdown summary of the entire knowledge base.

## 6. Constraints & Limits
- **File Size**: 3MB per file.
- **Source Length**: Max 120,000 characters per source.
- **Retrieval Limit**: Max 6 chunks (approx. 4000 characters) passed to the LLM per query.
- **Supported Formats**: Markdown, Plain Text, CSV, JSON.
