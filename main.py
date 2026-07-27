import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from control_arena import EvalMode
from bigcodebench_pbt_setting import (
    HELDOUT_TASK_IDS,
    MAIN_TASK_IDS,
    BigCodeBenchPBTSetting,
)
from config import Config
from evaluator import Evaluator
from run_artifacts import (
    build_manifest,
    write_candidate_pool,
    write_new_manifest,
    write_result_views,
    write_summary,
)
from candidate_pool import load_candidate_pool
from artifact_io import atomic_write_bytes


def main():
    parser = argparse.ArgumentParser(
        description="AI Control Benchmark: ControlArena & Inspect AI Implementation"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["main", "heldout"],
        default="main",
        help="Which curated BigCodeBench task subset to evaluate: 'main' (50 tasks, default) or "
        "'heldout' (5 tasks, zero overlap with 'main' or the PBT fewshot bank - for generalization checks)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only evaluate the first N task IDs from the chosen dataset (e.g. for a quick "
        "smoke test). Must match whatever --limit generated the --candidate-pool.",
    )
    parser.add_argument(
        "--trusted-model",
        type=str,
        default=Config().trusted_monitor_model,
        help="Trusted monitor model (e.g. 'openai/gpt-4o-mini', 'anthropic/claude-3-5-haiku-20241022')",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Suspicion threshold (default: 0.5)",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=100,
        help="Max examples for Hypothesis PBT",
    )
    parser.add_argument(
        "--pbt-prompt",
        type=str,
        default=Config().pbt_prompt_variant,
        help="PBT monitor prompt variant: name of a file under prompts/pbt_monitor/ (e.g. v1_baseline, v2_fewshot, v3_backdoor_focused)",
    )
    parser.add_argument(
        "--pbt-fewshot-k",
        type=int,
        default=Config().pbt_fewshot_k,
        help="Number of few-shot property examples (from prompts/pbt_monitor/fewshot_bank.json) to include in the PBT monitor prompt (0 = zero-shot)",
    )
    parser.add_argument(
        "--pbt-fewshot-seed",
        type=int,
        default=Config().pbt_fewshot_seed,
        help="Seed for which few-shot examples get sampled (for reproducible comparisons across prompt variants)",
    )
    parser.add_argument(
        "--pbt-execution-seed",
        type=int,
        default=Config().pbt_execution_seed,
        help="Base seed for deterministic Hypothesis examples (default: 0)",
    )
    parser.add_argument(
        "--tm-prompt",
        type=str,
        default=Config().tm_prompt_variant,
        help="Versioned code-only TM prompt under prompts/tm_monitor/. The default is "
        "the hardened prompt matched to PBT-Informed-TM; use 'v1_ai_control_paper' "
        "for the historical paper prompt.",
    )
    parser.add_argument(
        "--pbt-informed-tm-prompt",
        type=str,
        default=Config().pbt_informed_tm_prompt_variant,
        help="Hardened JSON-envelope prompt variant under prompts/tm_monitor/ for "
        "PBT-Informed-TM.",
    )
    parser.add_argument(
        "--max-concurrent-samples",
        type=int,
        default=Config().max_concurrent_samples,
        help="Max samples to run in parallel. Lower this (e.g. 5) if a run shows climbing HTTP retries "
        "with no progress - happens most with heavier-prompt monitors like PBT-Informed-TM against a "
        "provider's rate limit. Default: 2 (ten active containers).",
    )
    parser.add_argument(
        "--candidate-pool",
        dest="candidate_pool",
        type=str,
        default=None,
        help="Schema-v4 pool from prepare_candidate_pool.py containing one honest candidate, attack "
        "proposals, and forced/selective policy views. Required for paired comparisons.",
    )
    parser.add_argument(
        "--pbt-prompt-overrides",
        type=str,
        default=None,
        help="Per-protocol PBT monitor prompt override, comma-separated PROTOCOL=variant pairs. "
        "All PBT-consuming protocols in a paired run must resolve to the same variant.",
    )
    parser.add_argument(
        "--dump-explanations",
        action="store_true",
        help="Print each sample's scorer/monitor explanation text to the terminal instead of leaving it buried in the .eval log files",
    )
    parser.add_argument(
        "--protocols",
        type=str,
        default="TM,PBT,TM+PBT,PBT-Informed-TM",
        help="Comma-separated monitoring protocols chosen from TM, PBT, TM+PBT, and "
        "PBT-Informed-TM. The default runs the complete paired comparison; TM+PBT is a "
        "pure max-score derivation, while PBT-Informed-TM makes one integrated judgement "
        "from the candidate and the already-shared PBT evidence.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Immutable artifact directory; defaults to runs/<UTC timestamp>",
    )
    parser.add_argument(
        "--trusted-baseline-accuracy",
        type=float,
        default=None,
        help="Measured raw usefulness R(T) for paper-normalized usefulness",
    )
    parser.add_argument(
        "--untrusted-baseline-accuracy",
        type=float,
        default=None,
        help="Measured raw usefulness R(U) for paper-normalized usefulness",
    )
    parser.add_argument(
        "--attack-episode-subsample-rate",
        type=float,
        default=None,
        help="Explicit deployment sensitivity assumption. The paper used 1/12 for its APPS experiment; it is not inferred or applied by default.",
    )
    parser.add_argument(
        "--scenario-tasks",
        type=int,
        default=Config().scenario_tasks,
        help="Number of tasks in each simulated deployment",
    )
    parser.add_argument(
        "--safety-trials",
        type=int,
        default=Config().safety_trials,
        help="Number of Monte Carlo deployment trials; affects simulation precision only",
    )
    parser.add_argument(
        "--audit-budget",
        type=int,
        default=Config().audit_budget,
        help="Number of paid trusted audits available in each deployment",
    )
    parser.add_argument(
        "--free-initial-audits",
        type=int,
        default=Config().free_initial_audits,
        help="Number of initial deployment tasks audited without using the paid budget",
    )
    parser.add_argument(
        "--metric-seed",
        type=int,
        default=Config().metric_seed,
        help="Deterministic seed for deployment sampling and metric tie-breaking",
    )

    args = parser.parse_args()
    if not args.candidate_pool:
        parser.error("--candidate-pool is required")
    loaded_pool = load_candidate_pool(args.candidate_pool)
    pool_metadata = loaded_pool["metadata"]
    run_dir = args.run_dir or Path("runs") / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S.%fZ"
    )
    valid_protocols = {"TM", "PBT", "TM+PBT", "PBT-Informed-TM"}
    protocols = [p.strip() for p in args.protocols.split(",") if p.strip()]
    if not protocols:
        parser.error("--protocols must contain at least one protocol")
    if len(set(protocols)) != len(protocols):
        parser.error("--protocols must not contain duplicates")
    unknown = [p for p in protocols if p not in valid_protocols]
    if unknown:
        parser.error(
            f"Unknown protocol(s) {unknown} in --protocols. Choose from {sorted(valid_protocols)}."
        )

    pbt_prompt_overrides = {}
    if args.pbt_prompt_overrides:
        for pair in args.pbt_prompt_overrides.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                parser.error(
                    f"Invalid --pbt-prompt-overrides entry '{pair}': expected PROTOCOL=variant"
                )
            proto, variant = pair.split("=", 1)
            proto = proto.strip()
            if proto not in valid_protocols:
                parser.error(
                    f"Unknown protocol '{proto}' in --pbt-prompt-overrides. Choose from {sorted(valid_protocols)}."
                )
            if proto == "TM":
                parser.error(
                    "TM has no PBT component and cannot use a PBT prompt override"
                )
            pbt_prompt_overrides[proto] = variant.strip()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    task_ids = MAIN_TASK_IDS if args.dataset == "main" else HELDOUT_TASK_IDS
    if args.limit is not None:
        task_ids = task_ids[: args.limit]

    config = Config(
        task_ids=task_ids,
        untrusted_model=pool_metadata["untrusted_model"],
        trusted_monitor_model=args.trusted_model,
        suspicion_threshold=args.threshold,
        pbt_max_examples=args.max_examples,
        use_docker=True,
        pbt_prompt_variant=args.pbt_prompt,
        pbt_fewshot_k=args.pbt_fewshot_k,
        pbt_fewshot_seed=args.pbt_fewshot_seed,
        pbt_execution_seed=args.pbt_execution_seed,
        attack_prompt_variant=pool_metadata["attack_prompt_variant"],
        tm_prompt_variant=args.tm_prompt,
        pbt_informed_tm_prompt_variant=args.pbt_informed_tm_prompt,
        candidate_pool_path=args.candidate_pool,
        pbt_prompt_overrides=pbt_prompt_overrides,
        max_concurrent_samples=args.max_concurrent_samples,
        evidence_root=str(run_dir / "evidence"),
        eval_log_dir=str(run_dir / "eval_logs"),
        trusted_baseline_accuracy=args.trusted_baseline_accuracy,
        untrusted_baseline_accuracy=args.untrusted_baseline_accuracy,
        scenario_tasks=args.scenario_tasks,
        safety_trials=args.safety_trials,
        audit_budget=args.audit_budget,
        free_initial_audits=args.free_initial_audits,
        attack_episode_subsample_rate=args.attack_episode_subsample_rate,
        metric_seed=args.metric_seed,
    )
    # Commit provenance before RuntimeEvidenceStore creates any run subdirectories.
    manifest_setting = BigCodeBenchPBTSetting(
        task_ids=tuple(task_ids), sandbox_type="docker"
    )
    dataset_samples = list(manifest_setting.get_dataset(EvalMode.HONEST))
    manifest = build_manifest(
        config,
        protocols,
        dataset_samples=dataset_samples,
        run_id=run_dir.name,
    )
    bundled_pool_bytes = Path(config.candidate_pool_path).read_bytes()
    if (
        hashlib.sha256(bundled_pool_bytes).hexdigest()
        != manifest["candidate_pool"]["sha256"]
    ):
        raise RuntimeError("candidate pool changed while the run was starting")
    write_new_manifest(run_dir, manifest)
    evaluator = Evaluator(config, candidate_pool=loaded_pool)
    bundled_pool = (run_dir / "candidate_pool.json").resolve()
    atomic_write_bytes(bundled_pool, bundled_pool_bytes)
    candidate_references = write_candidate_pool(run_dir, loaded_pool, dataset_samples)

    console = Console()
    console.print(
        Panel(
            "[bold cyan]ControlArena Benchmark: Live Model & Dataset Pipeline[/bold cyan]\n"
            f"Dataset: [yellow]BigCodeBench ({args.dataset}, {len(task_ids)} tasks)[/yellow] | "
            f"Untrusted Model: [yellow]{config.untrusted_model}[/yellow] | "
            f"Trusted Monitor: [yellow]{config.trusted_monitor_model}[/yellow] | "
            f"Suspicion Threshold: [yellow]{config.suspicion_threshold}[/yellow]\n"
            f"PBT Prompt: [yellow]{config.pbt_prompt_variant}[/yellow] | "
            f"PBT Few-shot K: [yellow]{config.pbt_fewshot_k}[/yellow] | "
            f"Attack Prompt: [yellow]{config.attack_prompt_variant} (from pool)[/yellow]\n"
            f"Protocols: [yellow]{', '.join(protocols)}[/yellow]"
            + f" | Candidate Pool: [yellow]{config.candidate_pool_path}[/yellow]"
            + (
                f" | PBT Prompt Overrides: [yellow]{pbt_prompt_overrides}[/yellow]"
                if pbt_prompt_overrides
                else ""
            ),
            title="[bold magenta]ControlArena Evaluation[/bold magenta]",
        )
    )
    if config.untrusted_model.startswith(
        "mockllm/"
    ) or config.trusted_monitor_model.startswith("mockllm/"):
        console.print(
            "[bold yellow]MockLLM run: validates wiring only; results are not scientific measurements.[/bold yellow]"
        )

    summary = evaluator.run_experiment(
        dump_explanations=args.dump_explanations,
        console=console,
        protocols=protocols,
    )

    table = Table(title="Control Protocols Comparative Performance Summary")
    table.add_column("Control Protocol", style="bold cyan")
    table.add_column(
        f"Conditional Safety ({config.scenario_tasks:,} tasks)",
        style="bold green",
    )
    table.add_column("Raw Usefulness", style="bold cyan")
    table.add_column("Normalized Usefulness", style="cyan")
    table.add_column("Selected Policy", style="red")
    table.add_column("Forced Attack Recall", style="bold green")
    table.add_column("Forced Attack Evasion", style="bold red")
    table.add_column("Honest Flag Rate", style="yellow")
    table.add_column("Estimated Standalone Cost", style="bold yellow")

    for proto_name, m in summary.metrics_by_protocol.items():
        table.add_row(
            proto_name,
            (
                f"n/a ({m.safety_undefined_reason or 'estimate unavailable'})"
                if m.safety is None or m.safety_monte_carlo_ci95 is None
                else f"{m.safety * 100:.1f}% [MC {m.safety_monte_carlo_ci95[0] * 100:.1f}, {m.safety_monte_carlo_ci95[1] * 100:.1f}]"
            ),
            f"{m.raw_usefulness * 100:.1f}%",
            "n/a"
            if m.normalized_usefulness is None
            else f"{m.normalized_usefulness * 100:.1f}%",
            (
                f"attack {m.selected_attack_rate * 100:.1f}%; success n/a"
                if m.selected_attack_success_rate is None
                else (
                    f"attack {m.selected_attack_rate * 100:.1f}%; "
                    f"success {m.selected_attack_success_rate * 100:.1f}% "
                    f"({m.selected_successful_backdoors}/{m.selected_attack_attempts})"
                )
            ),
            (
                "n/a"
                if m.forced_successful_attack_detection_recall is None
                else f"{m.forced_successful_attack_detection_recall * 100:.1f}%"
            ),
            (
                "n/a"
                if m.forced_successful_attack_evasion_rate is None
                else f"{m.forced_successful_attack_evasion_rate * 100:.1f}%"
            ),
            "n/a" if m.honest_flag_rate is None else f"{m.honest_flag_rate * 100:.1f}%",
            "n/a"
            if m.estimated_standalone_cost_usd is None
            else f"${m.estimated_standalone_cost_usd:.4f}",
        )

    console.print(table)
    actual_cost = summary.estimated_evaluation_cost_usd
    console.print(
        "Estimated evaluation cost (shared calls counted once): "
        + ("n/a" if actual_cost is None else f"${actual_cost:.4f}")
    )
    write_summary(run_dir, summary)
    write_result_views(run_dir, summary, candidate_references, config)


if __name__ == "__main__":
    main()
