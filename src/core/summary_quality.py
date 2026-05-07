# -*- coding: utf-8 -*-
"""
LLM summary quality validation for conversation compression.

Provides metrics to evaluate how well an LLM-generated summary preserves
key information from the original conversation history:
- Keyword overlap ratio (how many important keywords appear in summary)
- Content length ratio (summary vs original, for compression assessment)
- Factual consistency check (named entities preserved)

Usage:
    from src.core.summary_quality import validate_summary

    metrics = validate_summary(
        original_messages=[...],
        summary="LLM-generated summary text",
    )
    print(metrics)  # {"keyword_overlap": 0.85, "length_ratio": 0.12, "quality": "good"}
"""

import re
from typing import Any, Dict, List


def _extract_keywords(text: str, min_length: int = 3) -> set:
    """Extract meaningful keywords from text (lowercase, alphanumeric tokens)."""
    words = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return {w for w in words if len(w) >= min_length}


def _extract_entities(text: str) -> set:
    """Extract potential named entities (capitalized words, GitHub-style owner/repo)."""
    entities = set()
    # GitHub-style owner/repo patterns
    repo_refs = re.findall(r"[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+", text)
    entities.update(repo_refs)
    # Capitalized words (potential proper nouns)
    capitalized = re.findall(r"\b[A-Z][a-z]{2,}\b", text)
    entities.update(capitalized)
    return entities


def validate_summary(
    original_messages: List[Dict[str, Any]],
    summary: str,
) -> Dict[str, Any]:
    """
    Validate the quality of an LLM-generated summary against original messages.

    Args:
        original_messages: List of message dicts with 'role' and 'content' keys.
        summary: The generated summary text.

    Returns:
        Dict with quality metrics:
        - keyword_overlap: 0.0-1.0 ratio of original keywords preserved in summary
        - entity_overlap: 0.0-1.0 ratio of named entities preserved
        - length_ratio: summary length / original total length (compression ratio)
        - quality: "good" (>=0.7), "fair" (>=0.5), or "poor" (<0.5)
    """
    # Extract all original text
    original_text = " ".join(
        msg.get("content", "") for msg in original_messages if msg.get("content")
    )

    if not original_text or not summary:
        return {
            "keyword_overlap": 0.0,
            "entity_overlap": 0.0,
            "length_ratio": 0.0,
            "quality": "poor",
            "reason": "Empty input",
        }

    # Keyword overlap
    orig_keywords = _extract_keywords(original_text)
    summary_keywords = _extract_keywords(summary)
    keyword_overlap = (
        len(orig_keywords & summary_keywords) / len(orig_keywords)
        if orig_keywords
        else 0.0
    )

    # Entity overlap
    orig_entities = _extract_entities(original_text)
    summary_entities = _extract_entities(summary)
    entity_overlap = (
        len(orig_entities & summary_entities) / len(orig_entities)
        if orig_entities
        else 0.0
    )

    # Length ratio (compression ratio)
    length_ratio = len(summary) / len(original_text) if original_text else 0.0

    # Overall quality assessment
    avg_score = (keyword_overlap + entity_overlap) / 2
    if avg_score >= 0.7:
        quality = "good"
    elif avg_score >= 0.5:
        quality = "fair"
    else:
        quality = "poor"

    return {
        "keyword_overlap": round(keyword_overlap, 3),
        "entity_overlap": round(entity_overlap, 3),
        "length_ratio": round(length_ratio, 3),
        "quality": quality,
        "orig_keyword_count": len(orig_keywords),
        "summary_keyword_count": len(summary_keywords),
    }


def validate_prompt_injection(
    summary: str,
    context_for_prompt: str,
) -> Dict[str, Any]:
    """
    Validate that a summary is correctly injected into the prompt context.

    Args:
        summary: The summary text.
        context_for_prompt: The full context string (includes summary + recent history).

    Returns:
        Dict with injection validation metrics.
    """
    if not summary:
        return {"injected": False, "reason": "Empty summary"}

    # Check if summary appears in the context
    injected = summary in context_for_prompt
    return {
        "injected": injected,
        "summary_length": len(summary),
        "context_length": len(context_for_prompt),
        "context_to_summary_ratio": round(
            len(context_for_prompt) / len(summary), 2
        )
        if summary
        else 0.0,
    }
