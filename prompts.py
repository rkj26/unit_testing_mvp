"""Loader for versioned, file-based prompts used by the PBT monitor and attack policy.

Prompts are plain text files under prompts/<category>/<variant>.txt so they can be
edited, diffed, and swapped via a CLI flag without touching any Python code. Two
categories exist today:

    prompts/pbt_monitor/*.txt    - instructs the trusted monitor LLM how to write
                                    Hypothesis property tests for a candidate solution.
                                    Rendered by this module (double-brace {{token}} style,
                                    chosen so embedded Python code containing single
                                    braces - dict/set literals - can't collide with
                                    substitution).
    prompts/attack_policy/*.txt  - passed straight through to ControlArena's
                                    attack_policy_builder(prompt=...), which does its
                                    own single-brace .format() substitution internally.
                                    Do not double-brace these.

prompts/pbt_monitor/fewshot_bank.json holds hand-written "good property" examples used
to few-shot the PBT monitor prompt. Bank problems are deliberately distinct from the
BigCodeBench task_ids in bigcodebench_pbt_setting.MAIN_TASK_IDS / HELDOUT_TASK_IDS so
few-shotting can't leak the answer for whatever problem is actually being scored.
"""

import json
import random
import re
from pathlib import Path
from typing import Optional

PROMPTS_ROOT = Path(__file__).parent / "prompts"
FEWSHOT_BANK_PATH = PROMPTS_ROOT / "pbt_monitor" / "fewshot_bank.json"


def list_prompt_variants(category: str) -> list[str]:
    """Lists available prompt variant names for a category (e.g. 'pbt_monitor')."""
    category_dir = PROMPTS_ROOT / category
    if not category_dir.is_dir():
        return []
    return sorted(p.stem for p in category_dir.glob("*.txt"))


def load_prompt(category: str, variant: str) -> str:
    """Loads the raw text of prompts/<category>/<variant>.txt.

    Raises FileNotFoundError with the list of valid variants if `variant` doesn't exist,
    so a CLI typo fails loudly instead of silently falling back to some default.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]+", category) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", variant
    ):
        raise ValueError("prompt category and variant must be simple names")
    path = PROMPTS_ROOT / category / f"{variant}.txt"
    if not path.exists():
        available = list_prompt_variants(category)
        raise FileNotFoundError(
            f"Unknown prompt variant '{variant}' for category '{category}'. "
            f"Available variants: {available or '(none found)'} "
            f"(looked in {path.parent})"
        )
    return path.read_text(encoding="utf-8")


def load_fewshot_bank() -> list[dict]:
    """Loads the hand-written good-property examples used to few-shot the PBT prompt."""
    if not FEWSHOT_BANK_PATH.exists():
        return []
    return json.loads(FEWSHOT_BANK_PATH.read_text(encoding="utf-8"))


def sample_fewshot_examples(
    k: int,
    exclude_entry_point: Optional[str] = None,
    seed: Optional[int] = None,
) -> list[dict]:
    """Samples up to k few-shot examples from the bank, excluding the problem under test.

    `exclude_entry_point` guards against a bank example accidentally being the same
    function as the one currently being scored (would leak the answer into the prompt).
    """
    bank = [
        e for e in load_fewshot_bank() if e.get("entry_point") != exclude_entry_point
    ]
    if k <= 0 or not bank:
        return []
    rng = random.Random(seed)
    return rng.sample(bank, k=min(k, len(bank)))


def format_fewshot_block(examples: list[dict]) -> str:
    """Renders a list of fewshot_bank.json entries into the {{few_shot_examples}} block."""
    if not examples:
        return "(no few-shot examples provided for this run - zero-shot)"

    blocks = []
    for i, ex in enumerate(examples, start=1):
        blocks.append(
            f"--- Example {i}: {ex['entry_point']} ---\n"
            f"Problem: {ex['problem_description']}\n\n"
            f"```python\n{ex['good_properties'].strip()}\n```\n\n"
            f"Why these properties are strong: {ex['commentary']}\n"
        )
    return "\n".join(blocks)


def render_pbt_prompt(
    variant: str,
    description: str,
    starter_code: str,
    entry_point: str,
    pbt_max_examples: int,
    fewshot_k: int = 0,
    fewshot_seed: Optional[int] = None,
) -> str:
    """Loads a prompts/pbt_monitor/<variant>.txt template and fills in all {{tokens}}.

    Few-shot examples (if fewshot_k > 0) are sampled fresh per call so different
    candidate solutions for the same problem can see different examples across a run;
    pass fewshot_seed for reproducibility in evaluation/comparison runs.
    """
    template = load_prompt("pbt_monitor", variant)
    if fewshot_k > 0 and "{{few_shot_examples}}" not in template:
        raise ValueError(
            f"prompt variant {variant!r} does not accept few-shot examples; choose a compatible template"
        )

    examples = sample_fewshot_examples(
        fewshot_k, exclude_entry_point=entry_point, seed=fewshot_seed
    )
    few_shot_block = format_fewshot_block(examples)

    rendered = template
    for token, value in [
        ("description", description),
        ("starter_code", starter_code),
        ("entry_point", entry_point),
        ("pbt_max_examples", str(pbt_max_examples)),
        ("few_shot_examples", few_shot_block),
    ]:
        rendered = rendered.replace("{{" + token + "}}", value)

    leftovers = sorted(set(re.findall(r"\{\{([A-Za-z0-9_]+)\}\}", rendered)))
    if leftovers:
        raise ValueError(f"unresolved prompt tokens in {variant!r}: {leftovers}")

    return rendered
