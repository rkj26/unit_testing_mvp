import argparse
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from bigcodebench_pbt_setting import HELDOUT_TASK_IDS, MAIN_TASK_IDS
from config import Config
from evaluator import Evaluator


def main():
    parser = argparse.ArgumentParser(
        description="AI Control Benchmark: ControlArena & Inspect AI Implementation"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["main", "heldout"],
        default="main",
        help="Which curated BigCodeBench task subset to evaluate: 'main' (10 tasks, default) or "
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
        help="Enable Docker container sandboxed execution",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Run parameter sweep and display Evasion Rate vs Cost Pareto frontier",
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
        default=None,
        help="Seed for which few-shot examples get sampled (for reproducible comparisons across prompt variants)",
    )
    parser.add_argument(
        "--tm-prompt",
        type=str,
        default=None,
        help="Prompt variant for the plain TM monitor (basic_monitor_builder): name of a file under "
        "prompts/tm_monitor/. Default (unset) uses ControlArena's own generic monitor prompt. "
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
        help="Directory to write generated PBT scripts into when --save-pbt-scripts is set (default: pbt_scripts/)",
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
        help="Directory to write submitted code into when --save-code is set (default: generated_code/)",
    )
    parser.add_argument(
        "--protocols",
        type=str,
        default="TM,PBT",
        help="Comma-separated list of protocols to run, chosen from TM, PBT, TE, Hybrid. "
        "Defaults to TM,PBT - the trusted-editor protocols (TE, Hybrid) are paused by default "
        "since they add an extra trusted-editor model call per sample. Pass e.g. "
        "--protocols TM,PBT,TE,Hybrid to re-enable them.",
    )

    args = parser.parse_args()

    valid_protocols = {"TM", "PBT", "TE", "Hybrid"}
    protocols = [p.strip() for p in args.protocols.split(",") if p.strip()]
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
            pbt_prompt_overrides[proto] = variant.strip()

    task_ids = MAIN_TASK_IDS if args.dataset == "main" else HELDOUT_TASK_IDS

    config = Config(
        task_ids=task_ids,
        untrusted_model=args.untrusted_model,
        trusted_monitor_model=args.trusted_model,
        suspicion_threshold=args.threshold,
        pbt_max_examples=args.max_examples,
        use_docker=args.docker,
        pbt_prompt_variant=args.pbt_prompt,
        pbt_fewshot_k=args.pbt_fewshot_k,
        pbt_fewshot_seed=args.pbt_fewshot_seed,
        attack_prompt_variant=args.attack_prompt,
        tm_prompt_variant=args.tm_prompt,
        attack_cache_path=args.attack_cache,
        pbt_prompt_overrides=pbt_prompt_overrides,
        pbt_save_scripts_dir=args.save_pbt_scripts_dir if args.save_pbt_scripts else None,
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

    evaluator = Evaluator(config)

    if args.sweep:
        console.print("[bold yellow]Running ControlArena Parameter Sweep (Threshold tau x PBT Budget N)...[/bold yellow]\n")
        sweep_points = evaluator.run_pareto_sweep(protocols=protocols)

        sweep_table = Table(title="Pareto Frontier: Evasion Rate vs Cost Analysis")
        sweep_table.add_column("Protocol", style="bold magenta")
        sweep_table.add_column("Threshold (tau)", style="cyan")
        sweep_table.add_column("PBT Budget (N)", style="cyan")
        sweep_table.add_column("Evasion Rate (Lower is Safer)", style="bold red")
        sweep_table.add_column("Main Task Utility", style="bold green")
        sweep_table.add_column("False Audit Rate", style="yellow")
        sweep_table.add_column("Avg Cost ($/problem)", style="bold yellow")

        for pt in sweep_points:
            sweep_table.add_row(
                pt.protocol,
                f"{pt.threshold:.2f}",
                str(pt.pbt_max_examples),
                f"{pt.evasion_rate * 100:.1f}%",
                f"{pt.main_task_utility * 100:.1f}%",
                f"{pt.false_audit_rate * 100:.1f}%",
                f"${pt.total_cost_usd:.4f}",
            )

        console.print(sweep_table)
    else:
        summary = evaluator.run_experiment(
            dump_explanations=args.dump_explanations,
            console=console,
            protocols=protocols,
            save_code_dir=args.save_code_dir if args.save_code else None,
        )

        table = Table(title="Control Protocols Comparative Performance Summary")
        table.add_column("Control Protocol", style="bold cyan")
        table.add_column("Evasion Rate (worked + undetected, lower is safer)", style="bold red")
        table.add_column("Attack Success Rate (worked, regardless of detection)", style="red")
        table.add_column("Main Task Utility", style="bold green")
        table.add_column("False Audit Rate", style="yellow")
        table.add_column("Avg Cost ($/problem)", style="bold yellow")

        for proto_name, m in summary.metrics_by_protocol.items():
            table.add_row(
                proto_name,
                f"{m.evasion_rate * 100:.1f}%",
                f"{m.attack_success_rate * 100:.1f}%",
                f"{m.main_task_utility * 100:.1f}%",
                f"{m.false_audit_rate * 100:.1f}%",
                f"${m.average_cost_usd:.4f}",
            )

        console.print(table)


if __name__ == "__main__":
    main()
