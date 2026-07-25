import argparse
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config import Config
from evaluator import Evaluator


def main():
    parser = argparse.ArgumentParser(
        description="AI Control Benchmark: ControlArena & Inspect AI Implementation"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to JSON dataset file containing APPS problem specifications",
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
        "--attack-prompt",
        type=str,
        default=Config().attack_prompt_variant,
        help="Attack policy prompt variant: name of a file under prompts/attack_policy/ (e.g. v1_default, v2_literal_trigger, v3_range_trigger) - controls what kind of backdoor the attacker is instructed to insert",
    )
    parser.add_argument(
        "--dump-explanations",
        action="store_true",
        help="Print each sample's scorer/monitor explanation text to the terminal instead of leaving it buried in the .eval log files",
    )

    args = parser.parse_args()

    config = Config(
        dataset_path=args.dataset,
        untrusted_model=args.untrusted_model,
        trusted_monitor_model=args.trusted_model,
        suspicion_threshold=args.threshold,
        pbt_max_examples=args.max_examples,
        use_docker=args.docker,
        pbt_prompt_variant=args.pbt_prompt,
        pbt_fewshot_k=args.pbt_fewshot_k,
        pbt_fewshot_seed=args.pbt_fewshot_seed,
        attack_prompt_variant=args.attack_prompt,
    )

    console = Console()
    console.print(
        Panel(
            "[bold cyan]ControlArena Benchmark: Live Model & Dataset Pipeline[/bold cyan]\n"
            f"Dataset: [yellow]{config.dataset_path}[/yellow] | "
            f"Untrusted Model: [yellow]{config.untrusted_model}[/yellow] | "
            f"Trusted Monitor: [yellow]{config.trusted_monitor_model}[/yellow] | "
            f"Suspicion Threshold: [yellow]{config.suspicion_threshold}[/yellow]\n"
            f"PBT Prompt: [yellow]{config.pbt_prompt_variant}[/yellow] | "
            f"PBT Few-shot K: [yellow]{config.pbt_fewshot_k}[/yellow] | "
            f"Attack Prompt: [yellow]{config.attack_prompt_variant}[/yellow]",
            title="[bold magenta]ControlArena Evaluation[/bold magenta]",
        )
    )

    evaluator = Evaluator(config)

    if args.sweep:
        console.print("[bold yellow]Running ControlArena Parameter Sweep (Threshold tau x PBT Budget N)...[/bold yellow]\n")
        sweep_points = evaluator.run_pareto_sweep()

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
        summary = evaluator.run_experiment(dump_explanations=args.dump_explanations, console=console)

        table = Table(title="Control Protocols Comparative Performance Summary")
        table.add_column("Control Protocol", style="bold cyan")
        table.add_column("Evasion Rate (Lower is Safer)", style="bold red")
        table.add_column("Main Task Utility", style="bold green")
        table.add_column("False Audit Rate", style="yellow")
        table.add_column("Avg Cost ($/problem)", style="bold yellow")

        for proto_name, m in summary.metrics_by_protocol.items():
            table.add_row(
                proto_name,
                f"{m.evasion_rate * 100:.1f}%",
                f"{m.main_task_utility * 100:.1f}%",
                f"{m.false_audit_rate * 100:.1f}%",
                f"${m.average_cost_usd:.4f}",
            )

        console.print(table)


if __name__ == "__main__":
    main()
