# src/parsing.py

import json
import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

def parse_failure_frequency_response(response_text: str) -> Dict[str, Any]:
    """
    Parses an alignment failure-mode risk estimation response.

    Expects the structured block produced by initial_failure_estimation.txt and
    subsequent_failure_estimation.txt:

        TECHNIQUE_MULTIPLIER_CENTRAL: <number>
        TECHNIQUE_MULTIPLIER_LOW: <number>
        TECHNIQUE_MULTIPLIER_HIGH: <number>
        TECHNIQUE_MULTIPLIER_CONFIDENCE: <0-1 float>
        CAUSAL_RATIONALE: <text>
        KEY_ASSUMPTIONS: <bullet list>
        BREAKDOWN_CONDITIONS: <text>
        OBSERVABILITY_NOTE: <text>

    The fields are mapped to the canonical result keys:
        estimate       <- TECHNIQUE_MULTIPLIER_CENTRAL
        minimum        <- TECHNIQUE_MULTIPLIER_LOW
        maximum        <- TECHNIQUE_MULTIPLIER_HIGH
        confidence     <- TECHNIQUE_MULTIPLIER_CONFIDENCE
        rationale      <- CAUSAL_RATIONALE
        key_assumptions       <- KEY_ASSUMPTIONS
        breakdown_conditions  <- BREAKDOWN_CONDITIONS
        observability_note    <- OBSERVABILITY_NOTE
    """
    cleaned = response_text.replace("**", "")
    # print(f"Parsing failure frequency response. Cleaned text:\n{cleaned}\n")
    result: Dict[str, Any] = {
        "estimate": None,
        "minimum": None,
        "maximum": None,
        "confidence": None,
        "rationale": "",
        "key_assumptions": "",
        "breakdown_conditions": "",
        "observability_note": "",
    }

    def _extract_float(pattern: str, text: str) -> Optional[float]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).strip().replace(",", ""))
            except (ValueError, IndexError):
                pass
        return None

    result["estimate"] = _extract_float(
        r"TECHNIQUE_EFFECT_CENTRAL\s*:\s*([+-]?[0-9,]*\.?[0-9]+)", cleaned
    )
    result["minimum"] = _extract_float(
        r"TECHNIQUE_EFFECT_LOW\s*:\s*([+-]?[0-9,]*\.?[0-9]+)", cleaned
    )
    result["maximum"] = _extract_float(
        r"TECHNIQUE_EFFECT_HIGH\s*:\s*([+-]?[0-9,]*\.?[0-9]+)", cleaned
    )
    result["confidence"] = _extract_float(
        r"TECHNIQUE_EFFECT_CONFIDENCE\s*:\s*([0-9]*\.?[0-9]+)", cleaned
    )

    # Multi-line text fields ─ capture everything up to the next labelled field or EOF
    def _extract_text(label_pattern: str, text: str) -> str:
        m = re.search(
            label_pattern + r"\s*:(.*?)(?=\n\s*[A-Z_]{3,}\s*:|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        return m.group(1).strip() if m else ""

    result["rationale"] = _extract_text(r"CAUSAL_RATIONALE", cleaned)
    result["key_assumptions"] = _extract_text(r"KEY_ASSUMPTIONS", cleaned)
    result["breakdown_conditions"] = _extract_text(r"BREAKDOWN_CONDITIONS", cleaned)
    result["observability_note"] = _extract_text(r"OBSERVABILITY_NOTE", cleaned)

    if result["estimate"] is None:
        logger.warning(
            "parse_failure_frequency_response: could not extract 'TECHNIQUE_EFFECT_CENTRAL'."
        )

    return result


def parse_defense_in_depth_response(response_text: str) -> Dict[str, Any]:
    """
    Parses a defense-in-depth (stacked techniques) estimation response.

    Expected format (from defense_in_depth_initial.txt / defense_in_depth_subsequent.txt):

        **Final estimated frequency**: <number>
        **Minimum value**: <number>
        **Maximum value**: <number>
        **Confidence in range**: <0-1 float>
        **Correlation assessment**: <text>
        **Residual risk**: <text>
        **Causal rationale**: <text>
        **Key assumptions**: <bullet list>

    Returns
    -------
    dict with keys:
        estimate, minimum, maximum, confidence,
        correlation_assessment, residual_risk, rationale, key_assumptions
    """
    cleaned = response_text.replace("**", "")

    result: Dict[str, Any] = {
        "estimate": None,
        "minimum": None,
        "maximum": None,
        "confidence": None,
        "correlation_assessment": "",
        "residual_risk": "",
        "rationale": "",
        "key_assumptions": "",
    }

    def _extract_float(pattern: str, text: str) -> Optional[float]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).strip().replace(",", ""))
            except (ValueError, IndexError):
                pass
        return None

    result["estimate"] = _extract_float(
        r"Final\s+estimated\s+frequency\s*:\s*(-?[0-9,]*\.?[0-9]+)", cleaned
    )
    result["minimum"] = _extract_float(
        r"Minimum\s+value\s*:\s*(-?[0-9,]*\.?[0-9]+)", cleaned
    )
    result["maximum"] = _extract_float(
        r"Maximum\s+value\s*:\s*(-?[0-9,]*\.?[0-9]+)", cleaned
    )
    result["confidence"] = _extract_float(
        r"Confidence\s+in\s+range\s*:\s*([0-9]*\.?[0-9]+)", cleaned
    )

    def _extract_text(label_pattern: str, text: str) -> str:
        m = re.search(
            label_pattern + r"\s*:(.*?)(?=\n\s*\*{0,2}[A-Z][A-Za-z\s]+\*{0,2}\s*:|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        return m.group(1).strip() if m else ""

    result["correlation_assessment"] = _extract_text(r"Correlation\s+assessment", cleaned)
    result["residual_risk"] = _extract_text(r"Residual\s+risk", cleaned)
    result["rationale"] = _extract_text(r"Causal\s+rationale", cleaned)
    result["key_assumptions"] = _extract_text(r"Key\s+assumptions", cleaned)

    if result["estimate"] is None:
        logger.warning(
            "parse_defense_in_depth_response: could not extract 'Final estimated frequency'."
        )

    return result


def parse_technique_ranking_response(
    response_text: str,
    expected_technique_ids: List[str],
) -> Dict[str, Any]:
    """Parses the alignment-technique ranking output for one failure mode.

    Expected structure in model output:

        RANKING_JSON: [
          {"technique_id": "rlhf", "reduction_pct": 12.0, "rank": 2, "rationale": "RLHF provides a moderate reduction by aligning the reward model, but is not perfect due to..."},
          ...
        ]
        RANKING_RATIONALE: <text>
    """
    result: Dict[str, Any] = {
        "rankings": [],
        "rationale": "",
        "error": None,
    }

    cleaned = response_text.replace("**", "")

    def _extract_text(label_pattern: str, text: str) -> str:
        m = re.search(
            label_pattern + r"\s*:(.*?)(?=\n\s*[A-Z_]{3,}\s*:|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        return m.group(1).strip() if m else ""

    result["rationale"] = _extract_text(r"RANKING_RATIONALE", cleaned)

    json_block = ""
    json_label_match = re.search(
        r"RANKING_JSON\s*:\s*(\[.*?\])",
        cleaned,
        re.IGNORECASE | re.DOTALL,
    )
    if json_label_match:
        json_block = json_label_match.group(1).strip()
    else:
        fallback_match = re.search(r"(\[\s*\{.*?\}\s*\])", cleaned, re.DOTALL)
        if fallback_match:
            json_block = fallback_match.group(1).strip()

    if not json_block:
        result["error"] = "Could not find RANKING_JSON block."
        return result

    try:
        parsed = json.loads(json_block)
    except json.JSONDecodeError as exc:
        result["error"] = f"Invalid RANKING_JSON format: {exc}"
        return result

    if not isinstance(parsed, list):
        result["error"] = "RANKING_JSON must be a list."
        return result

    expected_set = set(expected_technique_ids)
    normalized: List[Dict[str, Any]] = []
    seen_ids = set()

    for item in parsed:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("technique_id", "")).strip()
        if not tid or tid in seen_ids or tid not in expected_set:
            continue

        try:
            reduction = float(item.get("reduction_pct"))
        except (TypeError, ValueError):
            continue

        rank_raw = item.get("rank")
        rank_val: Optional[int]
        try:
            rank_val = int(rank_raw) if rank_raw is not None else None
        except (TypeError, ValueError):
            rank_val = None

        normalized.append(
            {
                "technique_id": tid,
                "reduction_pct": reduction,
                "rank": rank_val,
                "rationale": item.get("rationale", ""),
            }
        )
        seen_ids.add(tid)

    if len(normalized) != len(expected_technique_ids):
        missing = [tid for tid in expected_technique_ids if tid not in seen_ids]
        result["error"] = (
            "Ranking JSON missing techniques: " + ", ".join(missing)
            if missing
            else "Ranking JSON did not include all expected techniques."
        )
        return result

    normalized.sort(key=lambda r: r["reduction_pct"], reverse=True)
    for idx, row in enumerate(normalized, start=1):
        row["rank"] = idx

    result["rankings"] = normalized
    return result
