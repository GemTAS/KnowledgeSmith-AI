# KnowledgeSmith AI

**An Autonomous Knowledge Engineering Platform**

KnowledgeSmith AI transforms source material (code repositories, documentation collections) into a structured, interconnected, traceable knowledge base using the [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/open-knowledge-format) specification.

## Architecture

```
INGEST → EXTRACT → NORMALIZE → GENERATE KNOWLEDGE → LINK CONCEPTS → VALIDATE → EVALUATE → TRACK CHANGES
```

### Core Pipeline

1. **Ingestion** — Recursively scans directories for Markdown, Python, JSON, YAML, and plain-text files. Computes stable content hashes and source identifiers.
2. **Extraction** — Deterministic heuristic extractor identifies concepts from headings, declarations, imports, and identifiers. Optional LLM extractor uses Gemini for deeper semantic extraction.
3. **OKF Serialization** — Generates OKF v0.2–compliant Markdown+YAML artifacts with proper frontmatter, provenance tracking, and relationship links.
4. **Knowledge Graph** — Builds and traverses a directed concept graph with relationship discovery, neighbor lookup, and missing-target detection.
5. **Provenance & Trust** — Tracks extraction method, source hashes, verification status, and generation timestamps for every claim.
6. **Change Detection** — Compares source manifests to identify added, modified, and removed files. Marks affected artifacts as stale rather than deleting them.
7. **Validation** — Checks OKF schema conformance, broken links, duplicate concepts, and source-reference integrity.
8. **Evaluation** — Computes coverage, completeness, and quality metrics for the generated knowledge base.

## Quick Start

### Backend

```bash
cd backend
pip install -r ../requirements.txt
# Copy and configure environment
cp ../.env.example ../.env
# Run the API server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### CLI Scripts

```bash
# Build knowledge from a source directory
python scripts/build_knowledge.py ./examples/sample_project --output ./output

# Evaluate a knowledge base
python scripts/evaluate_knowledge.py ./output
```

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `KNOWLEDGESMITH_INGESTION_ROOT` | `.` | Root directory for source ingestion |
| `KNOWLEDGESMITH_OUTPUT_DIR` | `./output` | Output directory for knowledge artifacts |
| `KNOWLEDGESMITH_MAX_FILE_SIZE` | `1048576` | Maximum file size in bytes (1 MB) |
| `GOOGLE_API_KEY` | *(none)* | Gemini API key for LLM extraction |
| `KNOWLEDGESMITH_MODEL` | `gemini-2.5-flash` | Model name for LLM extraction |
| `KNOWLEDGESMITH_USE_LLM` | `false` | Enable LLM-based extraction |

## OKF Compliance

Knowledge artifacts follow the [OKF v0.2 specification](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md):

- Markdown files with YAML frontmatter
- Required `type` field per concept
- Optional `title`, `description`, `resource`, `tags` fields
- Provenance via `sources` and `generated` fields
- Trust tracking via `verified` and `status` fields
- Directory hierarchy with `index.md` for progressive disclosure
- Markdown links for inter-concept relationships

## Project Structure

```
knowledgesmith-ai/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI application entry
│       ├── config.py            # Pydantic settings
│       ├── api/                 # REST API layer
│       ├── core/                # Shared exceptions, logging
│       ├── ingestion/           # File scanning, chunking, hashing
│       ├── extraction/          # Concept extraction (deterministic + LLM)
│       ├── knowledge/           # OKF serialization, graph, validation
│       ├── agents/              # ADK agent orchestration
│       └── evaluation/          # Quality metrics
├── frontend/                    # React + TypeScript + Vite UI
├── tests/                       # Pytest test suite
├── examples/                    # Sample project for demonstrations
├── scripts/                     # CLI entry points
└── data/                        # Runtime data directory
```

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic
- **AI**: Google Generative AI (Gemini), deterministic fallback
- **Knowledge Format**: OKF v0.2
- **Frontend**: React, TypeScript, Vite
- **Storage**: Filesystem-based, JSON metadata, Git-compatible
- **Testing**: Pytest

## License

MIT License. See [LICENSE](LICENSE).
