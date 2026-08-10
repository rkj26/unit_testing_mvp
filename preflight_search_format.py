"""One real trigger-search call, to check the model complies with the line-per-input format.

The stdio format asks for a JSON string per line with newlines escaped. If the model writes raw
multi-line text instead, no line parses, the array fallback finds no bracket, and the task is lost
outright rather than merely shortened. That is worth one call to find out before a two-hour run.

  .venv/bin/python preflight_search_format.py [n_tasks]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from pipeline import model as model_mod
from pipeline import pbt
from pipeline.artifacts import ArtifactKind, ArtifactStore
from pipeline.config import Settings

POOL_RUN = Path("runs/uplanhard50-tlow-uhigh")


async def probe(trusted, problem) -> tuple[str, int, str | None, bool]:
    completion = await trusted.complete(pbt.search_prompt(problem), "trigger_search")
    space, error, salvaged = pbt.parse_search_space(completion)
    return completion, len(space or []), error, salvaged


async def main(n_tasks: int) -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    sys.argv = ["run.py"]
    settings = Settings(
        domain="apps",
        dataset="apps_pool_hard.json",
        run_id="preflight",
        t_model="openai-api/azureai/DeepSeek-V3.2",
        t_reasoning="low",
        u_model="openai-api/azureai/gpt-5.4",
        u_reasoning="high",
        gen_strategy="u_plans_t_writes",
    )
    config = settings.to_config("preflight")
    problems = ArtifactStore(POOL_RUN).load(ArtifactKind.PROBLEMS)[:n_tasks]
    trusted = model_mod.resolve(config.trusted_runtime(0))

    results = await asyncio.gather(*[probe(trusted, p) for p in problems])
    for problem, (completion, n, error, salvaged) in zip(problems, results):
        print(f"\n=== {problem.task_id}  n={n}  error={error!r}  salvaged={salvaged}")
        print("  head:", completion[:110].replace("\n", "\\n"))
        print("  tail:", completion[-70:].replace("\n", "\\n"))

    parsed = [n for _, n, _, _ in results]
    print(f"\ntasks {len(results)} · parsed ok {sum(1 for n in parsed if n)} · "
          f"inputs min {min(parsed)} median {sorted(parsed)[len(parsed) // 2]} max {max(parsed)} · "
          f"salvaged {sum(1 for *_, s in results if s)}")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
