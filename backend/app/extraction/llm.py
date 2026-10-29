"""LLM-based concept extractor using Google Gemini.

This adapter is optional — it requires a valid GOOGLE_API_KEY.
When unavailable or when errors occur, the pipeline falls back to
deterministic extraction.

Important: LLM-generated claims are always marked as UNVERIFIED.
The distinction between source-derived and model-generated information
is preserved in the extraction_method and verification_status fields.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

from backend.app.extraction.models import (
    Claim,
    Concept,
    ExtractionMethod,
    ExtractionResult,
    Relationship,
    SourceReference,
    VerificationStatus,
)
from backend.app.ingestion.loader import SourceFile

logger = logging.getLogger("knowledgesmith.extraction.llm")

_EXTRACTION_PROMPT = """You are a knowledge engineer. Analyze the following source file and extract structured knowledge.

Source file: {relative_path}
File type: {extension}

Content:
```
{content}
```

Extract the following as JSON:
{{
  "concepts": [
    {{
      "title": "concept name",
      "concept_type": "one of: Module, Class, Function, API, Configuration, Reference, Playbook",
      "description": "one-line description",
      "tags": ["tag1", "tag2"]
    }}
  ],
  "claims": [
    {{
      "statement": "a factual assertion found in the source",
      "start_line": null
    }}
  ],
  "relationships": [
    {{
      "source": "concept A title",
      "target": "concept B title",
      "type": "one of: imports, depends_on, implements, extends, related_to, configures"
    }}
  ]
}}

Rules:
- Only extract information that is directly present in the source.
- Do not invent information not found in the content.
- Keep descriptions factual and concise.
- Return valid JSON only, no markdown fences.
"""


def _is_available() -> bool:
    """Check whether the Gemini API key is configured."""
    return bool(os.environ.get("GOOGLE_API_KEY", ""))


def _call_gemini(prompt: str, model_name: str = "gemini-2.5-flash") -> Optional[str]:
    """Call the Gemini API and return the text response.

    Returns None on any failure (missing key, network, rate limit, etc.).
    """
    if not _is_available():
        logger.info("GOOGLE_API_KEY not set — LLM extraction unavailable.")
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=4096,
            ),
            request_options={"timeout": 60},
        )
        return response.text
    except ImportError:
        logger.warning("google-generativeai package not installed.")
        return None
    except Exception as exc:
        logger.warning("Gemini API call failed: %s", exc)
        return None


def _parse_llm_response(
    raw: str,
    sf: SourceFile,
) -> tuple[List[Concept], List[Claim], List[Relationship]]:
    """Parse the JSON response from the LLM, validating structure."""
    # Strip markdown fences if present.
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned invalid JSON: %s", exc)
        return [], [], []

    concepts: List[Concept] = []
    claims: List[Claim] = []
    relationships: List[Relationship] = []

    source_ref = SourceReference(
        source_id=sf.source_id,
        relative_path=sf.relative_path,
        content_hash=sf.content_hash,
    )

    # Parse concepts.
    for i, raw_c in enumerate(data.get("concepts", [])):
        if not isinstance(raw_c, dict) or "title" not in raw_c:
            continue
        import hashlib
        cid = hashlib.sha256(
            f"{sf.relative_path}::llm::{raw_c['title']}".encode()
        ).hexdigest()[:16]

        concepts.append(
            Concept(
                concept_id=cid,
                title=raw_c["title"],
                concept_type=raw_c.get("concept_type", "Reference"),
                description=raw_c.get("description", ""),
                tags=raw_c.get("tags", []),
                source_refs=[source_ref],
                extraction_method=ExtractionMethod.LLM,
            )
        )

    # Parse claims.
    for i, raw_cl in enumerate(data.get("claims", [])):
        if not isinstance(raw_cl, dict) or "statement" not in raw_cl:
            continue
        import hashlib
        claim_id = hashlib.sha256(
            f"{sf.source_id}::claim::{i}::{raw_cl['statement'][:50]}".encode()
        ).hexdigest()[:16]

        claims.append(
            Claim(
                claim_id=claim_id,
                statement=raw_cl["statement"],
                source_refs=[source_ref],
                extraction_method=ExtractionMethod.LLM,
                verification_status=VerificationStatus.UNVERIFIED,
            )
        )

    # Parse relationships.
    for raw_r in data.get("relationships", []):
        if not isinstance(raw_r, dict):
            continue
        src_title = raw_r.get("source", "")
        tgt_title = raw_r.get("target", "")
        if not src_title or not tgt_title:
            continue
        import hashlib
        src_id = hashlib.sha256(
            f"{sf.relative_path}::llm::{src_title}".encode()
        ).hexdigest()[:16]
        tgt_id = hashlib.sha256(
            f"{sf.relative_path}::llm::{tgt_title}".encode()
        ).hexdigest()[:16]

        relationships.append(
            Relationship(
                source_concept_id=src_id,
                target_concept_id=tgt_id,
                relationship_type=raw_r.get("type", "related_to"),
                extraction_method=ExtractionMethod.LLM,
            )
        )

    return concepts, claims, relationships


def extract_llm(
    files: List[SourceFile],
    model_name: str = "gemini-2.5-flash",
) -> ExtractionResult:
    """Run LLM-based extraction over a list of source files.

    Falls back gracefully when the API is unavailable.
    LLM-generated claims are always marked UNVERIFIED.
    """
    result = ExtractionResult(
        source_file_count=len(files),
        extraction_method=ExtractionMethod.LLM,
    )

    if not _is_available():
        result.errors.append("GOOGLE_API_KEY not configured — LLM extraction skipped.")
        return result

    for sf in files:
        prompt = _EXTRACTION_PROMPT.format(
            relative_path=sf.relative_path,
            extension=sf.extension,
            content=sf.content[:8000],  # Truncate very large files.
        )

        raw_response = _call_gemini(prompt, model_name=model_name)
        if raw_response is None:
            result.errors.append(f"LLM call failed for {sf.relative_path}")
            continue

        concepts, claims, relationships = _parse_llm_response(raw_response, sf)
        # Attach claims to the first concept if any.
        if concepts and claims:
            concepts[0].claims.extend(claims)
        result.concepts.extend(concepts)
        result.relationships.extend(relationships)

    logger.info(
        "LLM extraction: %d concepts, %d relationships from %d files",
        len(result.concepts),
        len(result.relationships),
        len(files),
    )
    return result
