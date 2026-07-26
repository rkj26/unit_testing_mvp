import argparse
from datetime import datetime, timezone
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from control_arena import EvalMode
from bigcodebench_pbt_setting import HELDOUT_TASK_IDS, MAIN_TASK_IDS
from config import Config
from evaluator import Evaluator
from run_artifacts import build_manifest, write_new_manifest, write_summary


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
        "--untrusted-model",
        type=str,
        default=Config().untrusted_model,
        help="Untrusted generator model (e.g. 'openai/o3-mini', 'anthropic/claude-3-7-sonnet-20250219')",
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
        "--docker",
        action="store_true",
        help="Deprecated compatibility flag; Docker isolation is now the default",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Run a threshold and PBT-budget safety/usefulness sweep",
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
        "--tm-prompt",
        type=str,
        default=Config().tm_prompt_variant,
        help="Prompt variant for the plain TM monitor (basic_monitor_builder): name of a file under "
        "prompts/tm_monitor/. Default uses ControlArena's own generic monitor prompt. "
        "'v1_ai_control_paper' uses the actual trusted-monitoring prompt from Greenblatt et al.'s AI Control paper.",
    )
    parser.add_argument(
        "--attack-prompt",
        type=str,
        default=Config().attack_prompt_variant,
        help="Attack policy prompt variant: name of a file under prompts/attack_policy/ (e.g. v1_default, v2_literal_trigger, v3_range_trigger) - controls what kind of backdoor the attacker is instructed to insert",
    )
    parser.add_argument(
        "--save-pbt-scripts",
        action="store_true",
        help="Write each generated Hypothesis property-test script to --save-pbt-scripts-dir, so you can "
        "see exactly what the PBT monitor tested instead of just pass/fail.",
    )
    parser.add_argument(
        "--save-pbt-scripts-dir",
        type=str,
        default="pbt_scripts",
        help="Run-directory subpath for generated PBT scripts when --save-pbt-scripts is set",
    )
    parser.add_argument(
        "--max-concurrent-samples",
        type=int,
        default=None,
        help="Max samples to run in parallel. Lower this (e.g. 5) if a run shows climbing HTTP retries "
        "with no progress - happens most with heavier-prompt monitors like PBT-Informed-TM against a "
        "provider's rate limit. Default (unset) uses Inspect's own default (~20).",
    )
    parser.add_argument(
        "--attack-cache",
        type=str,
        default=None,
        help="Path to a JSON cache from generate_attack_cache.py. When set, every protocol replays the "
        "exact same cached submission per problem instead of independently sampling the untrusted model "
        "- required for a true apples-to-apples comparison across protocols. --attack-prompt is ignored "
        "when this is set (the cache already baked in whatever prompt generated it).",
    )
    parser.add_argument(
        "--allow-unpaired-comparison",
        action="store_true",
        help="Exploratory only: compare protocols on independently sampled submissions",
    )
    parser.add_argument(
        "--pbt-prompt-overrides",
        type=str,
        default=None,
        help="Per-protocol PBT monitor prompt override, comma-separated PROTOCOL=variant pairs, e.g. "
        "'TE=v3_backdoor_focused,Hybrid=v2_fewshot'. Protocols not listed use --pbt-prompt.",
    )
    parser.add_argument(
        "--dump-explanations",
        action="store_true",
        help="Print each sample's scorer/monitor explanation text to the terminal instead of leaving it buried in the .eval log files",
    )
    parser.add_argument(
        "--save-code",
        action="store_true",
        help="Write each sample's submitted code (+ secret_input, if any) to its own .py file under --save-code-dir, "
        "so you can read exactly what the model generated without digging through the binary .eval log.",
    )
    parser.add_argument(
        "--save-code-dir",
        type=str,
        default="generated_code",
        help="Run-directory subpath for submitted code when --save-code is set",
    )
    parser.add_argument(
        "--protocols",
        type=str,
        default="TM,PBT",
        help="Comma-separated list of protocols to run, chosen from TM, PBT, TM+PBT, "
        "PBT-Informed-TM, TE, Hybrid. Defaults to TM,PBT - TE, Hybrid are paused by default "
        "(extra trusted-editor model call per sample); TM+PBT (parallel scores, combined via "
        "max()) and PBT-Informed-TM (one integrated judgment given both the code and the PBT "
        "test result) are opt-in, since each costs roughly double the trusted-model work of "
        "TM or PBT alone. Pass e.g. --protocols TM,PBT,PBT-Informed-TM to include it.",
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

    args = parser.parse_args()
    run_dir = args.run_dir or Path("runs") / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    for option, value in (
        ("--save-pbt-scripts-dir", args.save_pbt_scripts_dir),
        ("--save-code-dir", args.save_code_dir),
    ):
        artifact_path = Path(value)
        if artifact_path.is_absolute() or ".." in artifact_path.parts:
            parser.error(f"{option} must stay within --run-dir")

    valid_protocols = {"TM", "PBT", "TM+PBT", "PBT-Informed-TM", "TE", "Hybrid"}
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
                parser.error("TM has no PBT component and cannot use a PBT prompt override")
            pbt_prompt_overrides[proto] = variant.strip()

    task_ids = MAIN_TASK_IDS if args.dataset == "main" else HELDOUT_TASK_IDS

    config = Config(
        task_ids=task_ids,
        untrusted_model=args.untrusted_model,
        trusted_monitor_model=args.trusted_model,
        suspicion_threshold=args.threshold,
        pbt_max_examples=args.max_examples,
        use_docker=True,
        pbt_prompt_variant=args.pbt_prompt,
        pbt_fewshot_k=args.pbt_fewshot_k,
        pbt_fewshot_seed=args.pbt_fewshot_seed,
        attack_prompt_variant=args.attack_prompt,
        tm_prompt_variant=args.tm_prompt,
        attack_cache_path=args.attack_cache,
        allow_unpaired_protocol_comparison=args.allow_unpaired_comparison,
        pbt_prompt_overrides=pbt_prompt_overrides,
        max_concurrent_samples=args.max_concurrent_samples,
        pbt_save_scripts_dir=str(
            run_dir / args.save_pbt_scripts_dir
            if args.save_pbt_scripts
            else run_dir / "pbt_artifacts"
        ),
        eval_log_dir=str(run_dir / "eval_logs"),
        trusted_baseline_accuracy=args.trusted_baseline_accuracy,
        untrusted_baseline_accuracy=args.untrusted_baseline_accuracy,
        paper_attack_episode_subsample_rate=args.attack_episode_subsample_rate,
    )
    if (
        len(protocols) > 1
        and not config.attack_cache_path
        and not config.allow_unpaired_protocol_comparison
    ):
        parser.error(
            "multi-protocol comparisons require --attack-cache; use "
            "--allow-unpaired-comparison only for exploratory runs"
        )
    evaluator = Evaluator(config)
    write_new_manifest(
        run_dir,
        build_manifest(
            config, protocols, dataset_samples=evaluator.setting.get_dataset(EvalMode.HONEST)
        ),
    )

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
            f"Attack Prompt: [yellow]{config.attack_prompt_variant if not config.attack_cache_path else '(from cache)'}[/yellow]\n"
            f"Protocols: [yellow]{', '.join(protocols)}[/yellow]"
            + (f" | Attack Cache: [yellow]{config.attack_cache_path}[/yellow]" if config.attack_cache_path else "")
            + (f" | PBT Prompt Overrides: [yellow]{pbt_prompt_overrides}[/yellow]" if pbt_prompt_overrides else ""),
            title="[bold magenta]ControlArena Evaluation[/bold magenta]",
        )
    )

    if args.sweep:
        console.print("[bold yellow]Running ControlArena Parameter Sweep (Threshold tau x PBT Budget N)...[/bold yellow]\n")
        sweep_points = evaluator.run_pareto_sweep(protocols=protocols)

        sweep_table = Table(title="Safety / Usefulness Sweep")
        sweep_table.add_column("Protocol", style="bold magenta")
        sweep_table.add_column("Threshold (tau)", style="cyan")
        sweep_table.add_column("PBT Budget (N)", style="cyan")
        sweep_table.add_column("Conditional Safety", style="bold green")
        sweep_table.add_column("Raw Usefulness", style="bold cyan")
        sweep_table.add_column("Honest Flag Rate", style="yellow")
        sweep_table.add_column("Reported Model Cost", style="bold yellow")

        for pt in sweep_points:
            sweep_table.add_row(
                pt.protocol,
                f"{pt.threshold:.2f}",
                str(pt.pbt_max_examples),
                "n/a" if pt.safety is None else f"{pt.safety * 100:.1f}%",
                f"{pt.raw_usefulness * 100:.1f}%",
                f"{pt.honest_flag_rate * 100:.1f}%",
                "n/a" if pt.evaluation_model_cost_usd is None else f"${pt.evaluation_model_cost_usd:.4f}",
            )

        console.print(sweep_table)
        write_summary(run_dir, [point.model_dump(mode="json") for point in sweep_points])
    else:
        summary = evaluator.run_experiment(
            dump_explanations=args.dump_explanations,
            console=console,
            protocols=protocols,
            save_code_dir=(
                str(run_dir / args.save_code_dir) if args.save_code else None
            ),
        )

        table = Table(title="Control Protocols Comparative Performance Summary")
        table.add_column("Control Protocol", style="bold cyan")
        table.add_column("Conditional Safety (5,000 tasks)", style="bold green")
        table.add_column("Raw Usefulness", style="bold cyan")
        table.add_column("Normalized Usefulness", style="cyan")
        table.add_column("Successful Backdoors / Task", style="red")
        table.add_column("Undetected Backdoors / Task", style="bold red")
        table.add_column("Honest Flag Rate", style="yellow")
        table.add_column("Reported Model Cost", style="bold yellow")

        for proto_name, m in summary.metrics_by_protocol.items():
            table.add_row(
                proto_name,
                (
                    "n/a (set attack-rate assumption)"
                    if m.safety is None or m.safety_monte_carlo_ci95 is None
                    else f"{m.safety * 100:.1f}% [MC {m.safety_monte_carlo_ci95[0] * 100:.1f}, {m.safety_monte_carlo_ci95[1] * 100:.1f}]"
                ),
                f"{m.raw_usefulness * 100:.1f}%",
                "n/a" if m.normalized_usefulness is None else f"{m.normalized_usefulness * 100:.1f}%",
                f"{m.successful_backdoor_rate * 100:.1f}%",
                f"{m.per_task_undetected_backdoor_rate * 100:.1f}%",
                f"{m.honest_flag_rate * 100:.1f}%",
                "n/a" if m.evaluation_model_cost_usd is None else f"${m.evaluation_model_cost_usd:.4f}",
            )

        console.print(table)
        write_summary(run_dir, summary)


if __name__ == "__main__":
    main()
