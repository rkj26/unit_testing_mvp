"""Structured prompt boundaries for candidate-controlled monitor evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


DEFAULT_CODE_ONLY_TM_PROMPT_VARIANT = "v3_code_only_hardened"


def encode_untrusted_prompt_data(value: Mapping[str, Any]) -> str:
    """Encode data without allowing it to terminate the surrounding envelope."""

    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)
    return (
        encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )


def _render_evidence_prompt(
    template: str, evidence: Mapping[str, Any], *, monitor_label: str
) -> str:
    if set(_format_fields(template)) != {"evidence_json"}:
        raise ValueError(
            f"hardened {monitor_label} prompt must contain only {{evidence_json}}"
        )
    return template.format(evidence_json=encode_untrusted_prompt_data(evidence))


def render_code_only_tm_prompt(
    template: str, *, task_description: str, candidate_code: str
) -> str:
    """Render the code-only monitor through the shared untrusted-data boundary."""

    return _render_evidence_prompt(
        template,
        {
            "candidate_code": candidate_code,
            "task_description": task_description,
        },
        monitor_label="code-only TM",
    )


def render_pbt_informed_prompt(
    template: str,
    *,
    task_description: str,
    candidate_code: str,
    pbt_test_code: str,
    pbt_test_result: str,
) -> str:
    """Render the versioned informed-monitor prompt with one JSON data field."""

    return _render_evidence_prompt(
        template,
        {
            "candidate_code": candidate_code,
            "pbt_test_code": pbt_test_code,
            "pbt_test_result": pbt_test_result,
            "task_description": task_description,
        },
        monitor_label="PBT-informed",
    )


def _format_fields(template: str) -> list[str]:
    import string

    return [
        field_name
        for _, field_name, _, _ in string.Formatter().parse(template)
        if field_name is not None
    ]
