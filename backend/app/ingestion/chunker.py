"""Content chunking for large documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Chunk:
    """A segment of a source document."""

    content: str
    start_line: int
    end_line: int
    chunk_index: int
    source_id: str
    heading: str = ""


def chunk_by_headings(content: str, source_id: str) -> List[Chunk]:
    """Split *content* into chunks using markdown headings as boundaries.

    Falls back to a single chunk when no headings are found.
    """
    lines = content.split("\n")
    chunks: List[Chunk] = []
    current_lines: List[str] = []
    current_heading = ""
    start_line = 1

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            # Flush previous chunk.
            if current_lines:
                chunks.append(
                    Chunk(
                        content="\n".join(current_lines),
                        start_line=start_line,
                        end_line=i - 1,
                        chunk_index=len(chunks),
                        source_id=source_id,
                        heading=current_heading,
                    )
                )
            current_heading = stripped.lstrip("#").strip()
            current_lines = [line]
            start_line = i
        else:
            current_lines.append(line)

    # Flush last chunk.
    if current_lines:
        chunks.append(
            Chunk(
                content="\n".join(current_lines),
                start_line=start_line,
                end_line=len(lines),
                chunk_index=len(chunks),
                source_id=source_id,
                heading=current_heading,
            )
        )

    return chunks if chunks else [
        Chunk(
            content=content,
            start_line=1,
            end_line=len(lines),
            chunk_index=0,
            source_id=source_id,
        )
    ]


def chunk_by_size(content: str, source_id: str, max_chars: int = 4000) -> List[Chunk]:
    """Split *content* into chunks of roughly *max_chars* characters.

    Splits prefer line boundaries.
    """
    lines = content.split("\n")
    chunks: List[Chunk] = []
    current_lines: List[str] = []
    current_size = 0
    start_line = 1

    for i, line in enumerate(lines, start=1):
        line_len = len(line) + 1  # +1 for newline
        if current_size + line_len > max_chars and current_lines:
            chunks.append(
                Chunk(
                    content="\n".join(current_lines),
                    start_line=start_line,
                    end_line=i - 1,
                    chunk_index=len(chunks),
                    source_id=source_id,
                )
            )
            current_lines = []
            current_size = 0
            start_line = i

        current_lines.append(line)
        current_size += line_len

    if current_lines:
        chunks.append(
            Chunk(
                content="\n".join(current_lines),
                start_line=start_line,
                end_line=len(lines),
                chunk_index=len(chunks),
                source_id=source_id,
            )
        )

    return chunks
