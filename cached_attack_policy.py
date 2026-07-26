import json
from pathlib import Path
from typing import Any, Dict

from inspect_ai.agent import Agent, AgentState
from inspect_ai.model import ModelOutput
from inspect_ai.tool import Tool

from control_arena import control_agent, control_task_metadata


def load_attack_cache(path: str) -> Dict[str, Any]:
    """Load and validate a versioned cache produced by generate_attack_cache.py."""
    with open(path) as f:
        cache = json.load(f)
    if cache.get("schema_version") != 2:
        raise ValueError("attack cache must use schema_version=2; regenerate it")
    metadata = cache.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("attack cache is missing metadata")
    required_metadata = {
        "created_at",
        "task_ids",
        "untrusted_model",
        "trusted_model",
        "attack_prompt_variant",
        "attack_prompt_sha256",
        "repository_revision",
        "repository_dirty",
        "repository_diff_sha256",
    }
    missing_metadata = required_metadata.difference(metadata)
    if missing_metadata:
        raise ValueError(f"attack cache metadata is missing: {sorted(missing_metadata)}")
    if not isinstance(metadata["task_ids"], list) or not all(
        isinstance(task_id, str) for task_id in metadata["task_ids"]
    ):
        raise ValueError("attack cache metadata.task_ids must be a list of strings")
    if len(set(metadata["task_ids"])) != len(metadata["task_ids"]):
        raise ValueError("attack cache metadata.task_ids contains duplicates")
    for mode in ("honest", "attack"):
        if not isinstance(cache.get(mode), dict):
            raise ValueError(f"attack cache is missing {mode!r} submissions")
        for problem_id, entry in cache[mode].items():
            if not isinstance(problem_id, str) or not isinstance(entry, dict):
                raise ValueError(f"invalid {mode} cache entry")
            if not isinstance(entry.get("code"), str) or not entry["code"].strip():
                raise ValueError(f"cache entry {mode}/{problem_id} has no code")
            if entry.get("secret_input") is not None and not isinstance(
                entry["secret_input"], str
            ):
                raise ValueError(f"cache entry {mode}/{problem_id} has invalid secret_input")
        if set(cache[mode]) != set(metadata["task_ids"]):
            raise ValueError(f"attack cache {mode} keys do not match metadata.task_ids")
    return cache


@control_agent
def cached_policy_builder(cache: Dict[str, Any]):
    """Replays a pre-generated submission instead of calling the untrusted model.

    Looks up the current sample (by problem id and eval mode) in `cache` and emits
    exactly the same `code` / `secret_input` every time it's used. This is what
    makes an apples-to-apples comparison across protocols possible: TM, PBT, TE,
    and Hybrid all see byte-identical attacker output, so any difference in the
    resulting metrics is attributable to the monitor/editor, not to sampling
    variance in what the attacker happened to generate that run.
    """

    async def impl(state: AgentState, tools: list[Tool]) -> AgentState:
        task_metadata = control_task_metadata()
        mode_key = task_metadata.eval_mode.value  # "honest" or "attack"
        problem_id = task_metadata.main_task_name

        mode_cache = cache.get(mode_key, {})
        if problem_id not in mode_cache:
            raise KeyError(
                f"No cached '{mode_key}' submission for problem '{problem_id}' - "
                f"regenerate the cache with generate_attack_cache.py against the "
                f"current dataset first."
            )
        entry = mode_cache[problem_id]

        arguments: Dict[str, Any] = {"code": entry["code"]}
        if "secret_input" in entry and entry["secret_input"] is not None:
            arguments["secret_input"] = entry["secret_input"]

        state.output = ModelOutput.for_tool_call("cached", "submit", arguments)
        state._messages.append(state.output.message)
        return state

    return impl
