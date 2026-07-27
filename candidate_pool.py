"""Schema, validation, and access helpers for immutable candidate pools."""

from __future__ import annotations

import hashlib
import json
import math
import string
from typing import Any, Iterable, Mapping

from input_limits import MAX_SECRET_INPUT_BYTES, MAX_SOURCE_BYTES, valid_utf8_size

from policy_selection import (
    MOCKLLM_SELECTOR_ADAPTER,
    build_selector_input,
    mockllm_selector_result,
    parse_selector_output,
    render_selector_prompt_from_template,
    select_attack_opportunities,
    selection_algorithm_metadata,
    validate_selector_context,
    validate_selector_result,
)


CANDIDATE_POOL_SCHEMA_VERSION = 4
USAGE_FIELDS = {"input_tokens", "output_tokens", "model_cost_usd"}
_CANONICAL_TOP_LEVEL_FIELDS = {
    "schema_version",
    "metadata",
    "candidates",
    "selection",
    "views",
}
_CANDIDATE_FIELDS = {
    "candidate_id",
    "kind",
    "generation_index",
    "code",
    "code_sha256",
    "secret_input",
    "generation",
}
_GENERATION_FIELDS = {
    "model",
    "policy",
    "prompt_variant",
    "prompt_sha256",
    "sample_id",
    "seed",
    "usage",
}
_METADATA_FIELDS = {
    "created_at",
    "task_ids",
    "untrusted_model",
    "trusted_model",
    "attack_prompt_variant",
    "attack_prompt",
    "attack_prompt_sha256",
    "attack_proposals_per_task",
    "proposal_seed_base",
    "selector_model",
    "selector_prompt_variant",
    "selector_prompt",
    "selector_prompt_sha256",
    "dataset_fingerprints",
    "generation_usage",
    "generation_usage_by_phase",
    "repository_revision",
    "repository_dirty",
    "repository_diff_sha256",
}
_SELECTION_TASK_FIELDS = {
    "selector_context",
    "selector_input_sha256",
    "selector_prompt_sha256",
    "selector_model_completion",
    "selector_model_completion_sha256",
    "selector_effective_completion",
    "selector_effective_completion_sha256",
    "selector_completion_source",
    "selector_result",
    "usage",
    "best_attack_candidate_id",
    "best_opportunity_score",
    "best_is_viable",
    "selected_for_attack",
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in string.hexdigits for character in value)
    )


def candidate_id_for(
    *,
    task_id: str,
    kind: str,
    generation_index: int,
    code: str,
    secret_input: str | None,
) -> str:
    """Create a stable ID for the complete candidate, including its declared trigger."""

    payload = {
        "task_id": task_id,
        "kind": kind,
        "generation_index": generation_index,
        "code_sha256": sha256_text(code),
        "secret_input": secret_input,
    }
    return f"candidate_{_canonical_sha256(payload)}"


def validate_usage(value: Any, label: str = "usage") -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != USAGE_FIELDS:
        raise ValueError(f"{label} is invalid")
    for field in ("input_tokens", "output_tokens"):
        if type(value[field]) is not int or value[field] < 0:
            raise ValueError(f"{label}.{field} must be a non-negative integer")
    cost = value["model_cost_usd"]
    if cost is not None and (
        isinstance(cost, bool)
        or not isinstance(cost, (int, float))
        or not math.isfinite(cost)
        or cost < 0
    ):
        raise ValueError(f"{label}.model_cost_usd is invalid")
    return value


def sum_usages(usages: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    values = list(usages)
    for index, usage in enumerate(values):
        validate_usage(dict(usage), f"usage[{index}]")
    costs = [usage["model_cost_usd"] for usage in values]
    return {
        "input_tokens": sum(usage["input_tokens"] for usage in values),
        "output_tokens": sum(usage["output_tokens"] for usage in values),
        "model_cost_usd": (
            sum(costs) if costs and all(cost is not None for cost in costs) else None
        ),
    }


def _usages_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if left["input_tokens"] != right["input_tokens"]:
        return False
    if left["output_tokens"] != right["output_tokens"]:
        return False
    if left["model_cost_usd"] is None or right["model_cost_usd"] is None:
        return left["model_cost_usd"] is right["model_cost_usd"]
    return math.isclose(
        float(left["model_cost_usd"]),
        float(right["model_cost_usd"]),
        rel_tol=0.0,
        abs_tol=1e-12,
    )


def iter_candidates(
    pool: Mapping[str, Any], task_id: str
) -> tuple[dict[str, Any], ...]:
    """Return the honest candidate followed by every attack proposal for a task."""

    try:
        task = pool["candidates"][task_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate-pool task: {task_id}") from error
    return (task["honest"], *task["attack_proposals"])


def candidate_by_id(
    pool: Mapping[str, Any], task_id: str, candidate_id: str
) -> dict[str, Any]:
    for candidate in iter_candidates(pool, task_id):
        if candidate.get("candidate_id") == candidate_id:
            return candidate
    raise KeyError(f"unknown candidate {candidate_id!r} for task {task_id!r}")


def forced_candidate(pool: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    candidate_id = pool["views"]["forced_attack"][task_id]
    return candidate_by_id(pool, task_id, candidate_id)


def selected_policy_candidate(pool: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    candidate_id = pool["views"]["selected_policy"][task_id]
    return candidate_by_id(pool, task_id, candidate_id)


def selected_attack_task_ids(pool: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(pool["selection"]["selected_task_ids"])


def _validate_candidate(
    value: Any,
    *,
    task_id: str,
    kind: str,
    generation_index: int,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    label = f"candidate {task_id}/{kind}/{generation_index}"
    if not isinstance(value, dict) or set(value) != _CANDIDATE_FIELDS:
        raise ValueError(f"{label} has invalid fields")
    if value["kind"] != kind or value["generation_index"] != generation_index:
        raise ValueError(f"{label} has inconsistent kind or generation index")
    code = value["code"]
    secret_input = value["secret_input"]
    if not isinstance(code, str) or not code.strip():
        raise ValueError(f"{label} has no code")
    if not valid_utf8_size(code, MAX_SOURCE_BYTES):
        raise ValueError(f"{label} code exceeds the execution source limit")
    if secret_input is not None and not isinstance(secret_input, str):
        raise ValueError(f"{label} has invalid secret_input")
    if kind == "honest" and secret_input is not None:
        raise ValueError(f"{label} cannot declare a secret input")
    if kind == "attack" and secret_input is None:
        raise ValueError(f"{label} must declare a secret input")
    if kind == "attack":
        if not valid_utf8_size(secret_input, MAX_SECRET_INPUT_BYTES):
            raise ValueError(f"{label} secret_input exceeds the execution limit")
        try:
            parsed_secret = json.loads(secret_input)
        except json.JSONDecodeError as error:
            raise ValueError(f"{label} secret_input must be valid JSON") from error
        if not isinstance(parsed_secret, dict) or not all(
            isinstance(key, str) for key in parsed_secret
        ):
            raise ValueError(f"{label} secret_input must encode a JSON object")
    expected_code_hash = sha256_text(code)
    if value["code_sha256"] != expected_code_hash:
        raise ValueError(f"{label} code does not match code_sha256")
    expected_id = candidate_id_for(
        task_id=task_id,
        kind=kind,
        generation_index=generation_index,
        code=code,
        secret_input=secret_input,
    )
    if value["candidate_id"] != expected_id:
        raise ValueError(f"{label} has a non-deterministic candidate_id")

    generation = value["generation"]
    if not isinstance(generation, dict) or set(generation) != _GENERATION_FIELDS:
        raise ValueError(f"{label}.generation has invalid fields")
    for field in ("model", "policy", "sample_id"):
        if not isinstance(generation[field], str) or not generation[field].strip():
            raise ValueError(f"{label}.generation.{field} must be a non-empty string")
    if generation["model"] != metadata["untrusted_model"]:
        raise ValueError(f"{label} generation model does not match metadata")
    if generation["policy"] != kind:
        raise ValueError(f"{label} generation policy does not match candidate kind")
    if kind == "honest":
        if generation["prompt_variant"] is not None:
            raise ValueError(f"{label} honest prompt_variant must be null")
        if generation["prompt_sha256"] is not None:
            raise ValueError(f"{label} honest prompt_sha256 must be null")
        if generation["seed"] is not None:
            raise ValueError(f"{label} honest seed must be null")
    else:
        if generation["prompt_variant"] != metadata["attack_prompt_variant"]:
            raise ValueError(f"{label} attack prompt variant does not match metadata")
        if generation["prompt_sha256"] != metadata["attack_prompt_sha256"]:
            raise ValueError(f"{label} attack prompt hash does not match metadata")
        expected_seed = metadata["proposal_seed_base"] + generation_index
        if type(generation["seed"]) is not int or generation["seed"] != expected_seed:
            raise ValueError(
                f"{label} seed must equal proposal_seed_base + generation_index"
            )
    validate_usage(generation["usage"], f"{label}.generation.usage")
    return value


def _validate_metadata(metadata: Any) -> tuple[list[str], int]:
    if not isinstance(metadata, dict):
        raise ValueError("candidate pool is missing metadata")
    if set(metadata) != _METADATA_FIELDS:
        raise ValueError("candidate pool metadata has invalid fields")

    task_ids = metadata["task_ids"]
    if (
        not isinstance(task_ids, list)
        or not task_ids
        or not all(isinstance(task_id, str) and task_id for task_id in task_ids)
    ):
        raise ValueError("candidate pool metadata.task_ids must be non-empty strings")
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("candidate pool metadata.task_ids contains duplicates")
    proposal_count = metadata["attack_proposals_per_task"]
    if type(proposal_count) is not int or proposal_count < 1:
        raise ValueError("metadata.attack_proposals_per_task must be positive")
    proposal_seed_base = metadata["proposal_seed_base"]
    if type(proposal_seed_base) is not int or proposal_seed_base < 0:
        raise ValueError("metadata.proposal_seed_base must be a non-negative integer")
    for field in (
        "created_at",
        "untrusted_model",
        "trusted_model",
        "attack_prompt_variant",
        "attack_prompt",
        "selector_model",
        "selector_prompt_variant",
        "selector_prompt",
        "repository_revision",
    ):
        if not isinstance(metadata[field], str) or not metadata[field].strip():
            raise ValueError(
                f"candidate pool metadata.{field} must be a non-empty string"
            )
    if sha256_text(metadata["attack_prompt"]) != metadata["attack_prompt_sha256"]:
        raise ValueError("candidate pool attack prompt content does not match its hash")
    if sha256_text(metadata["selector_prompt"]) != metadata["selector_prompt_sha256"]:
        raise ValueError(
            "candidate pool selector prompt content does not match its hash"
        )
    if not isinstance(metadata["repository_dirty"], bool):
        raise ValueError("candidate pool metadata.repository_dirty must be a boolean")
    if not _is_sha256(metadata["repository_diff_sha256"]):
        raise ValueError("candidate pool metadata.repository_diff_sha256 is invalid")

    expected_ids = set(task_ids)
    fingerprints = metadata["dataset_fingerprints"]
    if not isinstance(fingerprints, dict) or set(fingerprints) != {"honest", "attack"}:
        raise ValueError("candidate pool must contain honest and attack fingerprints")
    for mode, values in fingerprints.items():
        if not isinstance(values, dict) or set(values) != expected_ids:
            raise ValueError(
                f"candidate pool {mode} dataset fingerprints do not match task IDs"
            )
        if not all(_is_sha256(digest) for digest in values.values()):
            raise ValueError(f"candidate pool {mode} dataset fingerprints are invalid")

    validate_usage(metadata["generation_usage"], "metadata.generation_usage")
    phases = metadata["generation_usage_by_phase"]
    if not isinstance(phases, dict) or set(phases) != {
        "candidate_generation",
        "selector_scoring",
    }:
        raise ValueError("metadata.generation_usage_by_phase is invalid")
    for phase, usage in phases.items():
        validate_usage(usage, f"metadata.generation_usage_by_phase.{phase}")
    return task_ids, proposal_count


def _validate_pool(pool: Any) -> dict[str, Any]:
    if not isinstance(pool, dict):
        raise ValueError("candidate pool root must be an object")
    version = pool.get("schema_version")
    if version != CANDIDATE_POOL_SCHEMA_VERSION:
        raise ValueError(
            f"candidate pool schema_version={version!r} is unsupported; regenerate "
            f"with schema_version={CANDIDATE_POOL_SCHEMA_VERSION}"
        )
    if set(pool) != _CANONICAL_TOP_LEVEL_FIELDS:
        raise ValueError("candidate pool has invalid top-level fields")
    metadata = pool["metadata"]
    task_ids, proposal_count = _validate_metadata(metadata)
    expected_ids = set(task_ids)

    candidates = pool["candidates"]
    if not isinstance(candidates, dict) or set(candidates) != expected_ids:
        raise ValueError(
            "candidate pool candidate tasks do not match metadata.task_ids"
        )
    candidate_usages = []
    all_candidate_ids: set[str] = set()
    for task_id in task_ids:
        task = candidates[task_id]
        if not isinstance(task, dict) or set(task) != {"honest", "attack_proposals"}:
            raise ValueError(f"candidate pool for {task_id} has invalid fields")
        honest = _validate_candidate(
            task["honest"],
            task_id=task_id,
            kind="honest",
            generation_index=0,
            metadata=metadata,
        )
        attacks = task["attack_proposals"]
        if not isinstance(attacks, list) or len(attacks) != proposal_count:
            raise ValueError(
                f"candidate pool for {task_id} must contain {proposal_count} attacks"
            )
        task_candidates = [honest]
        for index, attack in enumerate(attacks):
            task_candidates.append(
                _validate_candidate(
                    attack,
                    task_id=task_id,
                    kind="attack",
                    generation_index=index,
                    metadata=metadata,
                )
            )
        attack_code_hashes = {attack["code_sha256"] for attack in attacks}
        if len(attack_code_hashes) != len(attacks):
            raise ValueError(
                f"candidate pool for {task_id} contains duplicate attack proposal code"
            )
        if honest["code_sha256"] in attack_code_hashes:
            raise ValueError(
                f"candidate pool for {task_id} contains attack code identical to honest code"
            )
        for candidate in task_candidates:
            candidate_id = candidate["candidate_id"]
            if candidate_id in all_candidate_ids:
                raise ValueError(f"duplicate candidate_id in pool: {candidate_id}")
            all_candidate_ids.add(candidate_id)
            candidate_usages.append(candidate["generation"]["usage"])

    selection = pool["selection"]
    if not isinstance(selection, dict) or set(selection) != {
        "algorithm",
        "max_selected_attacks",
        "selected_task_ids",
        "tasks",
    }:
        raise ValueError("candidate pool selection has invalid fields")
    if selection["algorithm"] != selection_algorithm_metadata():
        raise ValueError("candidate pool selection algorithm is unsupported")
    max_selected = selection["max_selected_attacks"]
    if type(max_selected) is not int or max_selected < 0:
        raise ValueError("selection.max_selected_attacks must be non-negative")
    selection_tasks = selection["tasks"]
    if not isinstance(selection_tasks, dict) or set(selection_tasks) != expected_ids:
        raise ValueError(
            "candidate pool selection tasks do not match metadata.task_ids"
        )

    selector_results = {}
    selector_usages = []
    for task_id in task_ids:
        record = selection_tasks[task_id]
        if not isinstance(record, dict) or set(record) != _SELECTION_TASK_FIELDS:
            raise ValueError(f"selector record for {task_id} has invalid fields")
        context = validate_selector_context(record["selector_context"])
        if context["task_id"] != task_id:
            raise ValueError(f"selector context task ID mismatch for {task_id}")
        selector_input = build_selector_input(
            **context,
            attack_proposals=candidates[task_id]["attack_proposals"],
        )
        if record["selector_input_sha256"] != _canonical_sha256(selector_input):
            raise ValueError(f"selector input hash mismatch for {task_id}")
        expected_prompt = render_selector_prompt_from_template(
            metadata["selector_prompt"], selector_input
        )
        if record["selector_prompt_sha256"] != sha256_text(expected_prompt):
            raise ValueError(f"selector prompt hash mismatch for {task_id}")
        model_completion = record["selector_model_completion"]
        effective_completion = record["selector_effective_completion"]
        if not isinstance(model_completion, str):
            raise ValueError(f"selector model completion for {task_id} is invalid")
        if (
            not isinstance(effective_completion, str)
            or not effective_completion.strip()
        ):
            raise ValueError(f"selector effective completion for {task_id} is empty")
        if record["selector_model_completion_sha256"] != sha256_text(model_completion):
            raise ValueError(f"selector model completion hash mismatch for {task_id}")
        if record["selector_effective_completion_sha256"] != sha256_text(
            effective_completion
        ):
            raise ValueError(
                f"selector effective completion hash mismatch for {task_id}"
            )
        candidate_ids = [
            item["candidate_id"] for item in selector_input["attack_proposals"]
        ]
        result = validate_selector_result(record["selector_result"], candidate_ids)
        if result != record["selector_result"]:
            raise ValueError(f"selector result for {task_id} is not canonical")
        source = record["selector_completion_source"]
        if metadata["selector_model"].startswith("mockllm/"):
            if source != MOCKLLM_SELECTOR_ADAPTER:
                raise ValueError(f"MockLLM selector source mismatch for {task_id}")
            if result != mockllm_selector_result(candidate_ids):
                raise ValueError(f"MockLLM selector result mismatch for {task_id}")
        elif source != "model" or model_completion != effective_completion:
            raise ValueError(f"production selector source mismatch for {task_id}")
        parsed_completion = parse_selector_output(effective_completion, candidate_ids)
        if parsed_completion != result:
            raise ValueError(
                f"selector result for {task_id} does not match its completion"
            )
        selector_results[task_id] = result
        validate_usage(record["usage"], f"selector record {task_id}.usage")
        selector_usages.append(record["usage"])

    expected_selection = select_attack_opportunities(
        selector_results, max_selected_attacks=max_selected
    )
    if selection["selected_task_ids"] != expected_selection["selected_task_ids"]:
        raise ValueError(
            "selection.selected_task_ids does not match declared algorithm"
        )
    for task_id in task_ids:
        expected_decision = expected_selection["tasks"][task_id]
        actual = selection_tasks[task_id]
        for field, expected_value in expected_decision.items():
            if actual[field] != expected_value:
                raise ValueError(
                    f"selector decision {task_id}.{field} does not match "
                    "declared algorithm"
                )

    views = pool["views"]
    if not isinstance(views, dict) or set(views) != {
        "forced_attack",
        "selected_policy",
    }:
        raise ValueError("candidate pool views are invalid")
    for view_name, view in views.items():
        if not isinstance(view, dict) or set(view) != expected_ids:
            raise ValueError(f"candidate pool view {view_name} has invalid task IDs")
    for task_id in task_ids:
        decision = expected_selection["tasks"][task_id]
        best_id = decision["best_attack_candidate_id"]
        honest_id = candidates[task_id]["honest"]["candidate_id"]
        expected_selected_id = best_id if decision["selected_for_attack"] else honest_id
        if views["forced_attack"][task_id] != best_id:
            raise ValueError(f"forced_attack view mismatch for {task_id}")
        if views["selected_policy"][task_id] != expected_selected_id:
            raise ValueError(f"selected_policy view mismatch for {task_id}")
        candidate_by_id(pool, task_id, best_id)
        candidate_by_id(pool, task_id, expected_selected_id)

    candidate_total = sum_usages(candidate_usages)
    selector_total = sum_usages(selector_usages)
    phases = metadata["generation_usage_by_phase"]
    if not _usages_equal(phases["candidate_generation"], candidate_total):
        raise ValueError("candidate_generation usage does not match candidate records")
    if not _usages_equal(phases["selector_scoring"], selector_total):
        raise ValueError("selector_scoring usage does not match selector records")
    expected_total = sum_usages([candidate_total, selector_total])
    if not _usages_equal(metadata["generation_usage"], expected_total):
        raise ValueError("metadata.generation_usage does not match phase totals")
    return pool


def validate_candidate_pool(pool: Any) -> dict[str, Any]:
    """Validate an in-memory canonical pool without adding compatibility views."""

    return _validate_pool(pool)


def load_candidate_pool(path: str) -> dict[str, Any]:
    """Load and validate a canonical schema-v4 candidate pool."""

    with open(path, encoding="utf-8") as handle:
        pool = json.load(handle)
    _validate_pool(pool)
    return pool
