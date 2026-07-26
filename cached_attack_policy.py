import json
from pathlib import Path
from typing import Any, Dict

from inspect_ai.agent import Agent, AgentState
from inspect_ai.model import ModelOutput
from inspect_ai.tool import Tool

from control_arena import control_agent, control_task_metadata


def load_attack_cache(path: str) -> Dict[str, Dict[str, Any]]:
    """Loads a {"honest": {problem_id: {...}}, "attack": {problem_id: {...}}} cache
    produced by generate_attack_cache.py."""
    with open(path) as f:
        return json.load(f)


@control_agent
def cached_policy_builder(cache: Dict[str, Dict[str, Any]]):
    """Replays a pre-generated submission instead of calling the untrusted model.

    Looks up the current sample (by problem id and eval mode) in `cache` and emits
    exactly the same `code` / `secret_input` every time it's used. This is what
    makes an apples-to-apples comparison across protocols possible: TM, TM-PBT, TE,
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
