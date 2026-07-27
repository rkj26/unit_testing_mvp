from typing import Any, Dict

from inspect_ai.agent import AgentState
from inspect_ai.model import ModelOutput
from inspect_ai.tool import Tool

from control_arena import control_agent, control_task_metadata

from candidate_pool import candidate_by_id, forced_candidate, selected_policy_candidate


@control_agent
def candidate_pool_policy_builder(
    pool: Dict[str, Any],
    attack_view: str = "forced_attack",
    attack_candidate_ids: Dict[str, str] | None = None,
):
    """Replays a pre-generated submission instead of calling the untrusted model.

    Honest mode always replays the single honest candidate. Attack mode can replay
    either the best proposal on every task (``forced_attack``) or the selective
    policy, whose non-attack tasks resolve to their honest candidate. Explicit
    views keep detection-pool and deployment-policy measurements separate.
    """

    if attack_view not in {"forced_attack", "selected_policy"}:
        raise ValueError("attack_view must be 'forced_attack' or 'selected_policy'")
    if attack_candidate_ids is not None and attack_view != "forced_attack":
        raise ValueError(
            "explicit attack candidates cannot be combined with selected_policy"
        )

    async def impl(state: AgentState, tools: list[Tool]) -> AgentState:
        task_metadata = control_task_metadata()
        mode_key = task_metadata.eval_mode.value  # "honest" or "attack"
        problem_id = task_metadata.main_task_name

        try:
            if mode_key == "honest":
                entry = pool["candidates"][problem_id]["honest"]
            elif mode_key != "attack":
                raise KeyError(f"unsupported evaluation mode: {mode_key}")
            elif attack_candidate_ids is not None:
                entry = candidate_by_id(
                    pool, problem_id, attack_candidate_ids[problem_id]
                )
            elif attack_view == "forced_attack":
                entry = forced_candidate(pool, problem_id)
            else:
                entry = selected_policy_candidate(pool, problem_id)
        except KeyError as error:
            raise KeyError(
                f"No stored '{mode_key}' candidate for problem '{problem_id}' - "
                f"regenerate the pool with prepare_candidate_pool.py against the "
                f"current dataset first."
            ) from error

        arguments: Dict[str, Any] = {"code": entry["code"]}
        if "secret_input" in entry and entry["secret_input"] is not None:
            arguments["secret_input"] = entry["secret_input"]

        state.output = ModelOutput.for_tool_call("stored", "submit", arguments)
        state._messages.append(state.output.message)
        return state

    return impl
