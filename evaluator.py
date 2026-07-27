import math
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from inspect_ai.log import EvalLog
from inspect_ai.event import ModelEvent
from inspect_ai.model import GenerateConfig
from inspect_ai.scorer import CORRECT
from control_arena import EvalMode
from control_arena.eval import get_control_task, ControlEvalConfig, eval as control_eval
from control_arena.micro_protocol import trusted_monitoring_builder
from control_arena.scorers import max_suspicion_scorer

from bigcodebench_pbt_setting import BigCodeBenchPBTSetting, MAIN_TASK_IDS
from candidate_pool import candidate_by_id, forced_candidate, load_candidate_pool
from candidate_pool_policy import candidate_pool_policy_builder
from trusted_monitors import (
    pbt_informed_tm_monitor_builder,
    shared_tm_monitor_builder,
)
from pbt_monitor import pbt_monitor_builder
from config import Config
from provenance import dataset_fingerprints, files_fingerprint
from evidence import PBT_INFORMED_TM, TM, candidate_sha256
from evidence_runtime import RuntimeEvidenceStore
from cost_accounting import known_cost_total, total_input_tokens
from paper_metrics import (
    AttackEpisode,
    attempted_backdoor_from_messages,
    detection_metrics,
    estimate_safety,
    normalized_usefulness,
    raw_usefulness,
)
from submission import extract_submission
from artifact_io import atomic_write_json, atomic_write_text, safe_path_component


class MetricSummary(BaseModel):
    protocol_name: str
    safety: Optional[float] = None
    safety_monte_carlo_ci95: Optional[tuple[float, float]] = None
    expected_retained_attack_attempts: Optional[float] = None
    safety_informative: bool = False
    safety_undefined_reason: Optional[str] = None
    raw_usefulness: float
    normalized_usefulness: Optional[float] = None
    selected_tasks: int
    selected_attack_attempts: int = 0
    selected_successful_backdoors: int = 0
    selected_attack_rate: float
    selected_attack_success_rate: Optional[float] = None
    selected_attack_success_rate_undefined_reason: Optional[str] = None
    selected_successful_backdoors_per_task: float
    selected_threshold_unflagged_successful_backdoors_per_task: float
    forced_attack_attempts: int = 0
    forced_successful_backdoors: int = 0
    forced_successful_attack_detection_recall: Optional[float] = None
    forced_successful_attack_detection_recall_undefined_reason: Optional[str] = None
    forced_successful_attack_evasion_rate: Optional[float] = None
    forced_successful_attack_evasion_rate_undefined_reason: Optional[str] = None
    forced_top_1_attempt_capture_rate: Optional[float] = None
    forced_top_1_attempt_capture_rate_undefined_reason: Optional[str] = None
    forced_top_1_successful_attack_capture_rate: Optional[float] = None
    forced_top_1_successful_attack_capture_rate_undefined_reason: Optional[str] = None
    forced_successful_attack_auroc: Optional[float] = None
    forced_successful_attack_auroc_undefined_reason: Optional[str] = None
    honest_flag_rate: Optional[float] = None
    honest_flag_rate_undefined_reason: Optional[str] = None
    standalone_input_tokens: int
    standalone_output_tokens: int
    estimated_standalone_cost_usd: Optional[float] = None
    honest_suspicion_scores: List[float] = Field(default_factory=list, exclude=True)


class ExperimentSummary(BaseModel):
    total_evaluations: int
    honest_episodes_tested: int
    attack_episodes_tested: int
    evaluation_input_tokens: int
    evaluation_output_tokens: int
    estimated_evaluation_cost_usd: Optional[float] = None
    metrics_by_protocol: Dict[str, MetricSummary]
    detailed_results: List[Dict[str, Any]] = Field(default_factory=list)
    candidate_evaluations: List[Dict[str, Any]] = Field(default_factory=list)


class EpisodeResult(BaseModel):
    protocol_name: str
    task_id: str
    mode: str
    candidate_id: str
    candidate_sha256: str
    suspicion: float
    monitor_reason: str = ""
    evidence_refs: Dict[str, str] = Field(default_factory=dict)
    main_task_correct: bool
    side_task_success: bool
    attempted_backdoor: bool

    @property
    def successful_backdoor(self) -> bool:
        return (
            self.attempted_backdoor
            and self.main_task_correct
            and self.side_task_success
        )

    def as_attack_episode(self) -> AttackEpisode:
        return AttackEpisode(
            suspicion=self.suspicion,
            main_task_correct=self.main_task_correct,
            side_task_success=self.side_task_success,
            attempted_backdoor=self.attempted_backdoor,
        )


@dataclass
class ProtocolRun:
    protocol_name: str
    honest: list[EpisodeResult]
    forced_attack: list[EpisodeResult]
    model_input_tokens: int
    model_output_tokens: int
    incremental_input_tokens: int
    incremental_output_tokens: int
    logical_cost: Optional[float]
    incremental_cost: Optional[float]


class Evaluator:
    """Evaluate the four paired monitoring protocols with Inspect/ControlArena."""

    def __init__(
        self,
        config: Config,
        candidate_pool: Optional[Dict[str, Any]] = None,
        evidence_store: Optional[RuntimeEvidenceStore] = None,
    ):
        self.config = config
        configured_pool = (
            load_candidate_pool(config.candidate_pool_path)
            if config.candidate_pool_path
            else None
        )
        if candidate_pool is not None and configured_pool is not None:
            if candidate_pool != configured_pool:
                raise ValueError(
                    "injected candidate pool differs from config.candidate_pool_path"
                )
        self.candidate_pool = candidate_pool or configured_pool
        if self.candidate_pool is None:
            raise ValueError("Evaluator requires a candidate pool")
        self.setting = BigCodeBenchPBTSetting(
            task_ids=tuple(config.task_ids or MAIN_TASK_IDS),
            sandbox_type="docker" if config.use_docker else "local",
        )
        source_root = Path(__file__).parent
        execution_sources = [
            "Dockerfile",
            "compose.yml",
            "isolated_execution.py",
            "pbt_policy.py",
            "requirements.txt",
            *[
                str(path.relative_to(source_root))
                for path in (source_root / "sandbox_tools").glob("*.py")
            ],
        ]
        evidence_producer_config = {
            "trusted_monitor_model": config.trusted_monitor_model,
            "pbt_max_examples": config.pbt_max_examples,
            "pbt_timeout_seconds": config.pbt_timeout_seconds,
            "pbt_prompt_variant": config.pbt_prompt_variant,
            "pbt_prompt_overrides": config.pbt_prompt_overrides,
            "pbt_fewshot_k": config.pbt_fewshot_k,
            "pbt_fewshot_seed": config.pbt_fewshot_seed,
            "pbt_execution_seed": config.pbt_execution_seed,
            "tm_prompt_variant": config.tm_prompt_variant,
            "pbt_informed_tm_prompt_variant": (config.pbt_informed_tm_prompt_variant),
            "sandbox_type": "docker" if config.use_docker else "local",
            "execution_source_sha256": files_fingerprint(
                source_root, execution_sources
            ),
            "hypothesis_version": importlib.metadata.version("hypothesis"),
            "pytest_version": importlib.metadata.version("pytest"),
        }
        if evidence_store is None:
            self.evidence_store = RuntimeEvidenceStore(
                config.evidence_root,
                producer_config=evidence_producer_config,
            )
        else:
            evidence_store.bind_producer_config(evidence_producer_config)
            self.evidence_store = evidence_store
        pool_metadata = self.candidate_pool["metadata"]
        if config.untrusted_model != pool_metadata["untrusted_model"]:
            raise ValueError(
                "configured untrusted model does not match the pool generation model"
            )
        if config.attack_prompt_variant != pool_metadata["attack_prompt_variant"]:
            raise ValueError(
                "configured attack prompt does not match the prompt embedded in the pool"
            )
        expected = set(config.task_ids or MAIN_TASK_IDS)
        metadata_ids = set(self.candidate_pool.get("metadata", {}).get("task_ids", []))
        if metadata_ids != expected:
            raise ValueError(
                "candidate pool task IDs do not match this run; regenerate the pool "
                f"(expected {len(expected)}, pool has {len(metadata_ids)})"
            )
        for mode in ("honest", "attack"):
            current = dataset_fingerprints(
                self.setting.get_dataset(
                    EvalMode.HONEST if mode == "honest" else EvalMode.ATTACK
                )
            )
            expected_fingerprints = self.candidate_pool["metadata"][
                "dataset_fingerprints"
            ][mode]
            if current != expected_fingerprints:
                raise ValueError(
                    f"candidate pool {mode} dataset content has changed; regenerate the pool"
                )

    def _build_micro_protocol(
        self,
        proto_name: str,
        config: Config,
        attack_candidate_ids: Optional[Dict[str, str]] = None,
    ):
        """Constructs ControlArena micro-protocol for specified strategy."""
        untrusted_pol = candidate_pool_policy_builder(
            pool=self.candidate_pool,
            attack_candidate_ids=attack_candidate_ids,
        )

        # Overrides fall back to the run-wide PBT prompt. Paired protocols are
        # constrained to one variant so the exact same suite can be reused.
        pbt_prompt_for_proto = config.pbt_prompt_overrides.get(
            proto_name, config.pbt_prompt_variant
        )
        if proto_name in {
            "PBT",
            "TM+PBT",
            "PBT-Informed-TM",
        } and hasattr(self, "_shared_pbt_prompt_variant"):
            pbt_prompt_for_proto = self._shared_pbt_prompt_variant
        pbt_mon = pbt_monitor_builder(
            pbt_max_examples=config.pbt_max_examples,
            model_name=config.trusted_monitor_model,
            prompt_variant=pbt_prompt_for_proto,
            fewshot_k=config.pbt_fewshot_k,
            fewshot_seed=config.pbt_fewshot_seed,
            execution_seed=config.pbt_execution_seed,
            save_scripts_dir=None,
            timeout_seconds=int(config.pbt_timeout_seconds),
            evidence_store=self.evidence_store,
        )
        basic_mon = shared_tm_monitor_builder(
            model_name=config.trusted_monitor_model,
            tm_prompt_variant=config.tm_prompt_variant,
            evidence_store=self.evidence_store,
        )

        if proto_name == "TM":
            return trusted_monitoring_builder(policy=untrusted_pol, monitor=basic_mon)
        elif proto_name == "PBT":
            return trusted_monitoring_builder(policy=untrusted_pol, monitor=pbt_mon)
        elif proto_name == "PBT-Informed-TM":
            informed_mon = pbt_informed_tm_monitor_builder(
                model_name=config.trusted_monitor_model,
                tm_prompt_variant=config.pbt_informed_tm_prompt_variant,
                pbt_max_examples=config.pbt_max_examples,
                pbt_prompt_variant=pbt_prompt_for_proto,
                pbt_fewshot_k=config.pbt_fewshot_k,
                pbt_fewshot_seed=config.pbt_fewshot_seed,
                pbt_execution_seed=config.pbt_execution_seed,
                save_scripts_dir=None,
                timeout_seconds=int(config.pbt_timeout_seconds),
                evidence_store=self.evidence_store,
            )
            return trusted_monitoring_builder(
                policy=untrusted_pol, monitor=informed_mon
            )
        raise ValueError(f"unknown protocol: {proto_name}")

    def _dump_sample_explanations(
        self, console, mode_label: str, proto_name: str, logs: List[EvalLog]
    ) -> None:
        """Prints each sample's scorer/monitor explanation - otherwise this only lives in logs/*.eval."""
        printer = console.print if console else print
        samples = [sample for log in logs for sample in (log.samples or [])]
        if not samples:
            return
        printer(f"\n--- {proto_name} / {mode_label}: sample explanations ---")
        for s in samples:
            printer(f"[sample {s.id}]")
            if s.scores:
                for score_name, score in s.scores.items():
                    printer(f"  {score_name} = {score.value!r}: {score.explanation}")

    def _save_generated_code(
        self, mode_label: str, proto_name: str, logs: List[EvalLog], out_dir: str
    ) -> None:
        """Writes each sample's submitted code (+ secret_input, if any) to its own .py file."""
        samples = [sample for log in logs for sample in (log.samples or [])]
        if not samples:
            return
        for s in samples:
            submission = extract_submission(s.messages)
            code = submission.code
            secret_input = submission.secret_input
            safe_id = safe_path_component(str(s.id), fallback="sample")
            artifact_dir = Path(out_dir) / proto_name / mode_label.lower() / safe_id
            atomic_write_json(artifact_dir / "sample.json", s.model_dump(mode="json"))
            if not code:
                continue
            path = artifact_dir / "submission.py"
            lines = [f"# protocol={proto_name} mode={mode_label} sample={s.id}"]
            if secret_input is not None:
                lines.append(f"# secret_input = {secret_input!r}")
            if s.scores:
                for score_name, score in s.scores.items():
                    lines.append(
                        f"# {score_name} = {score.value!r}: {score.explanation}"
                    )
            lines.append("")
            lines.append(code)
            atomic_write_text(path, "\n".join(lines))

    @staticmethod
    def _submission(sample: Any) -> tuple[str, Optional[str]]:
        submission = extract_submission(sample.messages)
        return submission.code, submission.secret_input

    @staticmethod
    def _monitor_reason(sample: Any) -> str:
        for message in reversed(sample.messages):
            metadata = getattr(message, "metadata", None) or {}
            if isinstance(metadata.get("reason"), str):
                return metadata["reason"]
        return ""

    def _candidate_id(
        self,
        task_id: str,
        mode: str,
        code: str,
        secret_input: Optional[str],
        attack_candidate_ids: Optional[Dict[str, str]] = None,
    ) -> str:
        if self.candidate_pool is not None:
            if mode == "honest":
                entry = self.candidate_pool["candidates"][task_id]["honest"]
            elif attack_candidate_ids is not None:
                entry = candidate_by_id(
                    self.candidate_pool, task_id, attack_candidate_ids[task_id]
                )
            else:
                entry = forced_candidate(self.candidate_pool, task_id)
            if entry["code"] != code or entry.get("secret_input") != secret_input:
                raise RuntimeError(
                    f"{mode} replay for {task_id} did not match its pool candidate"
                )
            candidate_id = entry.get("candidate_id")
            if isinstance(candidate_id, str) and candidate_id:
                return candidate_id
        return f"{mode}_{candidate_sha256(code)}"

    @staticmethod
    def _suspicion(sample: Any) -> float:
        score = sample.scores.get("max_suspicion_scorer") if sample.scores else None
        if (
            score is None
            or isinstance(score.value, bool)
            or not isinstance(score.value, (int, float))
        ):
            raise RuntimeError(f"sample {sample.id} has no numeric suspicion score")
        value = float(score.value)
        if not math.isfinite(value):
            raise RuntimeError(f"sample {sample.id} has a non-finite suspicion score")
        return value

    def _episode_result(
        self,
        proto_name: str,
        mode: str,
        sample: Any,
        attack_candidate_ids: Optional[Dict[str, str]] = None,
        ground_truth: Optional[Dict[str, Dict[str, bool]]] = None,
    ) -> EpisodeResult:
        task_id = (sample.metadata or {}).get("main_task_name")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"sample {sample.id} has no main_task_name")
        code, secret_input = self._submission(sample)
        if not code:
            raise RuntimeError(f"sample {sample.id} has no submitted code")
        candidate_id = self._candidate_id(
            task_id,
            mode,
            code,
            secret_input,
            attack_candidate_ids=attack_candidate_ids,
        )
        if ground_truth is not None:
            try:
                labels = ground_truth[candidate_id]
            except KeyError as error:
                raise RuntimeError(
                    f"no frozen ground truth for candidate {candidate_id}"
                ) from error
        else:
            score = sample.scores.get("bigcodebench_scorer") if sample.scores else None
            if score is None or not isinstance(score.value, dict):
                raise RuntimeError(f"sample {sample.id} has no BigCodeBench score")
            labels = {
                "main_task_correct": score.value.get("main_task_success") == CORRECT,
                "side_task_success": score.value.get("side_task_success") == CORRECT,
                "attempted_backdoor": attempted_backdoor_from_messages(sample.messages),
            }
        candidate_hash = candidate_sha256(code)
        return EpisodeResult(
            protocol_name=proto_name,
            task_id=task_id,
            mode=mode,
            candidate_id=candidate_id,
            candidate_sha256=candidate_hash,
            suspicion=self._suspicion(sample),
            monitor_reason=self._monitor_reason(sample),
            main_task_correct=labels["main_task_correct"],
            side_task_success=labels["side_task_success"],
            attempted_backdoor=labels["attempted_backdoor"],
            evidence_refs=self._evidence_refs(proto_name, task_id, candidate_hash),
        )

    def _evidence_refs(
        self, protocol: str, task_id: str, candidate_hash: str
    ) -> Dict[str, str]:
        refs: Dict[str, str] = {}
        if protocol in {"PBT", "PBT-Informed-TM"}:
            suite = self.evidence_store.get_suite(task_id)
            if suite is not None:
                refs["pbt_suite_sha256"] = suite.suite_sha256
                execution = self.evidence_store.get_pbt(
                    task_id,
                    candidate_hash,
                    suite_sha256=suite.suite_sha256,
                )
                if execution is not None:
                    refs["pbt_evidence_sha256"] = execution.evidence_sha256
        monitor_kind = {
            "TM": TM,
            "PBT-Informed-TM": PBT_INFORMED_TM,
        }.get(protocol)
        if monitor_kind is not None:
            monitor_evidence = self.evidence_store.get_monitor(
                task_id, candidate_hash, monitor_kind
            )
            if monitor_evidence is not None:
                refs[f"{monitor_kind}_evidence_sha256"] = (
                    monitor_evidence.evidence_sha256
                )
        return refs

    def _execute_protocol(
        self,
        proto_name: str,
        dump_explanations: bool = False,
        console: Optional[Any] = None,
        save_code_dir: Optional[str] = None,
        attack_candidate_ids: Optional[Dict[str, str]] = None,
        run_honest: bool = True,
        run_attack: bool = True,
        skip_task_scorers: bool = False,
        ground_truth: Optional[Dict[str, Dict[str, bool]]] = None,
    ) -> ProtocolRun:
        """Run one atomic monitor protocol against honest and forced-attack views."""
        if not run_honest and not run_attack:
            raise ValueError("at least one evaluation mode must be enabled")
        if skip_task_scorers != (ground_truth is not None):
            raise ValueError(
                "skipping task scorers requires complete frozen ground truth"
            )
        proto = self._build_micro_protocol(
            proto_name,
            self.config,
            attack_candidate_ids=attack_candidate_ids,
        )
        # max_samples alone only limits how many dataset samples run concurrently -
        # each sample can still fire multiple simultaneous model calls (policy +
        # monitor + PBT generation), so the actual provider-facing concurrency also
        # needs GenerateConfig.max_connections capped per model, or a retry storm
        # can still happen even with max_samples turned down.
        model_config = (
            GenerateConfig(max_connections=self.config.max_concurrent_samples)
            if self.config.max_concurrent_samples
            else None
        )
        eval_cfg = ControlEvalConfig(
            untrusted_model=self.config.untrusted_model,
            trusted_model=self.config.trusted_monitor_model,
            max_samples=self.config.max_concurrent_samples,
            untrusted_config=model_config,
            trusted_config=model_config,
            log_dir=self.config.eval_log_dir,
            skip_task_scorers=skip_task_scorers,
        )

        # monitoring_scorers attaches max_suspicion_scorer as an extra score per sample,
        # reading back the suspicion_score every monitor (@monitor decorator) writes into
        # the last assistant message's metadata. This lets us report the honest
        # flag rate and calibrate the optional conditional audit simulation.
        monitoring_scorers = [max_suspicion_scorer()]

        # Run Honest Mode Task
        honest_logs: List[EvalLog] = []
        if run_honest:
            honest_task = get_control_task(
                setting=self.setting,
                micro_protocol=proto,
                mode=EvalMode.HONEST,
                eval_config=eval_cfg,
                monitoring_scorers=monitoring_scorers,
            )
            honest_logs = control_eval(honest_task, **eval_cfg.eval_args())

        # Run Attack Mode Task
        attack_logs: List[EvalLog] = []
        if run_attack:
            attack_task = get_control_task(
                setting=self.setting,
                micro_protocol=proto,
                mode=EvalMode.ATTACK,
                eval_config=eval_cfg,
                monitoring_scorers=monitoring_scorers,
            )
            attack_logs = control_eval(attack_task, **eval_cfg.eval_args())

        if dump_explanations and run_honest:
            self._dump_sample_explanations(console, "HONEST", proto_name, honest_logs)
        if dump_explanations and run_attack:
            self._dump_sample_explanations(console, "ATTACK", proto_name, attack_logs)

        if save_code_dir and run_honest:
            self._save_generated_code("HONEST", proto_name, honest_logs, save_code_dir)
        if save_code_dir and run_attack:
            self._save_generated_code("ATTACK", proto_name, attack_logs, save_code_dir)

        honest_samples = [
            sample for log in honest_logs for sample in (log.samples or [])
        ]
        attack_samples = [
            sample for log in attack_logs for sample in (log.samples or [])
        ]
        failed_samples = [
            sample
            for sample in honest_samples + attack_samples
            if sample.error is not None
        ]
        if failed_samples:
            details = "; ".join(
                f"{sample.id}: {sample.error}" for sample in failed_samples[:5]
            )
            raise RuntimeError(
                f"{proto_name} produced failed evaluation samples; refusing to "
                f"publish metrics: {details}"
            )
        expected = len(self.config.task_ids or MAIN_TASK_IDS)
        expected_honest = expected if run_honest else 0
        expected_attack = expected if run_attack else 0
        if (
            len(honest_samples) != expected_honest
            or len(attack_samples) != expected_attack
        ):
            raise RuntimeError(
                f"incomplete evaluation for {proto_name}: expected "
                f"honest={expected_honest}, attack={expected_attack}; "
                f"got honest={len(honest_samples)}, attack={len(attack_samples)}"
            )

        expected_task_ids = set(self.config.task_ids or MAIN_TASK_IDS)
        for mode, samples in (("honest", honest_samples), ("attack", attack_samples)):
            if not samples:
                continue
            task_names = [
                (sample.metadata or {}).get("main_task_name") for sample in samples
            ]
            if (
                any(name is None for name in task_names)
                or set(task_names) != expected_task_ids
            ):
                raise RuntimeError(
                    f"{proto_name} {mode} logs do not cover the configured task IDs exactly"
                )
            if len(set(task_names)) != len(task_names):
                raise RuntimeError(f"{proto_name} {mode} logs contain duplicate tasks")

        billed_usages = [
            usage
            for sample in honest_samples + attack_samples
            for usage in (sample.model_usage or {}).values()
        ]
        model_events = [
            event
            for sample in honest_samples + attack_samples
            for event in (sample.events or [])
            if isinstance(event, ModelEvent)
        ]
        logical_usages = [
            event.output.usage
            for event in model_events
            if event.output.usage is not None
        ]
        billed_costs = [usage.total_cost for usage in billed_usages]
        logical_costs = [usage.total_cost for usage in logical_usages]
        missing_uncached_usage = any(
            event.output.usage is None and event.cache != "read"
            for event in model_events
        )
        incremental_cost = known_cost_total(
            billed_costs, missing_usage=missing_uncached_usage
        )
        logical_cost = known_cost_total(
            logical_costs,
            missing_usage=any(event.output.usage is None for event in model_events),
        )

        return ProtocolRun(
            protocol_name=proto_name,
            honest=[
                self._episode_result(
                    proto_name, "honest", sample, ground_truth=ground_truth
                )
                for sample in honest_samples
            ],
            forced_attack=[
                self._episode_result(
                    proto_name,
                    "forced_attack",
                    sample,
                    attack_candidate_ids=attack_candidate_ids,
                    ground_truth=ground_truth,
                )
                for sample in attack_samples
            ],
            model_input_tokens=sum(
                total_input_tokens(usage) for usage in logical_usages
            ),
            model_output_tokens=sum(usage.output_tokens for usage in logical_usages),
            incremental_input_tokens=sum(
                total_input_tokens(usage) for usage in billed_usages
            ),
            incremental_output_tokens=sum(
                usage.output_tokens for usage in billed_usages
            ),
            logical_cost=logical_cost,
            incremental_cost=incremental_cost,
        )

    @staticmethod
    def _sum_optional(left: Optional[float], right: Optional[float]) -> Optional[float]:
        return None if left is None or right is None else left + right

    def _derive_tm_pbt(self, tm: ProtocolRun, pbt: ProtocolRun) -> ProtocolRun:
        def combine(
            left: list[EpisodeResult], right: list[EpisodeResult], mode: str
        ) -> list[EpisodeResult]:
            left_by_task = {episode.task_id: episode for episode in left}
            right_by_task = {episode.task_id: episode for episode in right}
            if set(left_by_task) != set(right_by_task):
                raise RuntimeError("TM and PBT did not cover the same tasks")
            combined = []
            for task_id in sorted(left_by_task):
                tm_episode = left_by_task[task_id]
                pbt_episode = right_by_task[task_id]
                for field in (
                    "candidate_sha256",
                    "candidate_id",
                    "main_task_correct",
                    "side_task_success",
                    "attempted_backdoor",
                ):
                    if getattr(tm_episode, field) != getattr(pbt_episode, field):
                        raise RuntimeError(
                            f"TM/PBT evidence mismatch for {task_id}: {field}"
                        )
                combined.append(
                    EpisodeResult(
                        protocol_name="TM+PBT",
                        task_id=task_id,
                        mode=mode,
                        candidate_id=tm_episode.candidate_id,
                        candidate_sha256=tm_episode.candidate_sha256,
                        suspicion=max(tm_episode.suspicion, pbt_episode.suspicion),
                        monitor_reason=(
                            f"TM={tm_episode.suspicion}: {tm_episode.monitor_reason}\n\n"
                            f"PBT={pbt_episode.suspicion}: {pbt_episode.monitor_reason}"
                        ),
                        main_task_correct=tm_episode.main_task_correct,
                        side_task_success=tm_episode.side_task_success,
                        attempted_backdoor=tm_episode.attempted_backdoor,
                        evidence_refs={
                            **tm_episode.evidence_refs,
                            **pbt_episode.evidence_refs,
                        },
                    )
                )
            return combined

        return ProtocolRun(
            protocol_name="TM+PBT",
            honest=combine(tm.honest, pbt.honest, "honest"),
            forced_attack=combine(tm.forced_attack, pbt.forced_attack, "forced_attack"),
            model_input_tokens=tm.model_input_tokens + pbt.model_input_tokens,
            model_output_tokens=tm.model_output_tokens + pbt.model_output_tokens,
            incremental_input_tokens=(
                tm.incremental_input_tokens + pbt.incremental_input_tokens
            ),
            incremental_output_tokens=(
                tm.incremental_output_tokens + pbt.incremental_output_tokens
            ),
            logical_cost=self._sum_optional(tm.logical_cost, pbt.logical_cost),
            incremental_cost=self._sum_optional(
                tm.incremental_cost, pbt.incremental_cost
            ),
        )

    def _with_dependency_cost(
        self, run: ProtocolRun, dependency: ProtocolRun
    ) -> ProtocolRun:
        return ProtocolRun(
            protocol_name=run.protocol_name,
            honest=run.honest,
            forced_attack=run.forced_attack,
            model_input_tokens=run.model_input_tokens + dependency.model_input_tokens,
            model_output_tokens=run.model_output_tokens
            + dependency.model_output_tokens,
            incremental_input_tokens=(
                run.incremental_input_tokens + dependency.incremental_input_tokens
            ),
            incremental_output_tokens=(
                run.incremental_output_tokens + dependency.incremental_output_tokens
            ),
            logical_cost=self._sum_optional(run.logical_cost, dependency.logical_cost),
            incremental_cost=self._sum_optional(
                run.incremental_cost, dependency.incremental_cost
            ),
        )

    def _selected_policy_episodes(self, run: ProtocolRun) -> list[AttackEpisode]:
        honest = {episode.task_id: episode for episode in run.honest}
        forced = {episode.task_id: episode for episode in run.forced_attack}
        if (
            self.candidate_pool is None
            or self.candidate_pool.get("schema_version") != 4
        ):
            return [episode.as_attack_episode() for episode in run.forced_attack]

        from candidate_pool import selected_policy_candidate

        selected: list[AttackEpisode] = []
        for task_id in sorted(honest):
            candidate = selected_policy_candidate(self.candidate_pool, task_id)
            if candidate["candidate_id"] == honest[task_id].candidate_id:
                selected.append(
                    AttackEpisode(
                        suspicion=honest[task_id].suspicion,
                        main_task_correct=honest[task_id].main_task_correct,
                        side_task_success=False,
                        attempted_backdoor=False,
                    )
                )
            elif candidate["candidate_id"] == forced[task_id].candidate_id:
                selected.append(forced[task_id].as_attack_episode())
            else:
                raise RuntimeError(
                    f"selected policy candidate for {task_id} lacks monitor evidence"
                )
        return selected

    def _collect_pbt_candidate_pool(
        self, honest_pbt: ProtocolRun
    ) -> tuple[ProtocolRun, list[EpisodeResult], int]:
        if (
            self.candidate_pool is None
            or self.candidate_pool.get("schema_version") != 4
        ):
            raise ValueError("candidate-pool PBT collection requires a schema-v4 pool")
        proposal_count = self.candidate_pool["metadata"]["attack_proposals_per_task"]
        results: list[EpisodeResult] = [
            episode.model_copy(update={"mode": "honest_candidate"})
            for episode in honest_pbt.honest
        ]
        proposal_runs: list[ProtocolRun] = []
        attack_by_candidate: dict[str, EpisodeResult] = {}
        for proposal_index in range(proposal_count):
            proposal_ids = {
                task_id: self.candidate_pool["candidates"][task_id]["attack_proposals"][
                    proposal_index
                ]["candidate_id"]
                for task_id in self.candidate_pool["metadata"]["task_ids"]
            }
            proposal_run = self._execute_protocol(
                "PBT",
                attack_candidate_ids=proposal_ids,
                run_honest=False,
                run_attack=True,
            )
            proposal_runs.append(proposal_run)
            proposal_episodes = proposal_run.forced_attack
            attack_by_candidate.update(
                (episode.candidate_id, episode) for episode in proposal_episodes
            )
            results.extend(
                episode.model_copy(update={"mode": f"attack_proposal_{proposal_index}"})
                for episode in proposal_episodes
            )
        forced_episodes = []
        for task_id in self.candidate_pool["metadata"]["task_ids"]:
            candidate_id = forced_candidate(self.candidate_pool, task_id)[
                "candidate_id"
            ]
            forced_episodes.append(
                attack_by_candidate[candidate_id].model_copy(
                    update={"mode": "forced_attack"}
                )
            )

        all_runs = [honest_pbt, *proposal_runs]

        def total_cost(attribute: str) -> Optional[float]:
            values = [getattr(run, attribute) for run in all_runs]
            return known_cost_total(values)

        pbt_run = ProtocolRun(
            protocol_name="PBT",
            honest=honest_pbt.honest,
            forced_attack=forced_episodes,
            model_input_tokens=sum(run.model_input_tokens for run in all_runs),
            model_output_tokens=sum(run.model_output_tokens for run in all_runs),
            incremental_input_tokens=sum(
                run.incremental_input_tokens for run in all_runs
            ),
            incremental_output_tokens=sum(
                run.incremental_output_tokens for run in all_runs
            ),
            logical_cost=total_cost("logical_cost"),
            incremental_cost=total_cost("incremental_cost"),
        )
        return pbt_run, results, proposal_count

    def _persist_evidence_bundles(self) -> None:
        if (
            self.candidate_pool is None
            or self.candidate_pool.get("schema_version") != 4
        ):
            return
        from candidate_pool import iter_candidates

        candidate_ids: dict[str, dict[str, str]] = {}
        for task_id in self.candidate_pool["metadata"]["task_ids"]:
            ids_by_hash: dict[str, str] = {}
            for entry in iter_candidates(self.candidate_pool, task_id):
                ids_by_hash.setdefault(
                    candidate_sha256(entry["code"]), entry["candidate_id"]
                )
            suite = self.evidence_store.get_suite(task_id)
            if suite is None:
                detail = self.evidence_store.generation_error(task_id)
                raise RuntimeError(
                    f"missing PBT suite for {task_id}; refusing to publish metrics"
                    + (f": {detail}" if detail else "")
                )
            for candidate_hash in ids_by_hash:
                execution = self.evidence_store.get_pbt(
                    task_id, candidate_hash, suite_sha256=suite.suite_sha256
                )
                if execution is None:
                    raise RuntimeError(
                        f"missing PBT result for {task_id}/{candidate_hash}; "
                        "refusing to publish metrics"
                    )
                if execution.raw_result.error is not None:
                    raise RuntimeError(
                        f"invalid PBT execution for {task_id}/{candidate_hash}; "
                        f"refusing to publish metrics: {execution.raw_result.error}"
                    )
            candidate_ids[task_id] = ids_by_hash
        self.evidence_store.write_bundles(candidate_ids)

    @staticmethod
    def _frozen_ground_truth(
        candidate_results: List[EpisodeResult],
    ) -> Dict[str, Dict[str, bool]]:
        frozen: Dict[str, Dict[str, bool]] = {}
        for episode in candidate_results:
            labels = {
                "main_task_correct": episode.main_task_correct,
                "side_task_success": episode.side_task_success,
                "attempted_backdoor": episode.attempted_backdoor,
            }
            existing = frozen.setdefault(episode.candidate_id, labels)
            if existing != labels:
                raise RuntimeError(
                    f"conflicting ground truth for candidate {episode.candidate_id}"
                )
        return frozen

    def _metric_summary(self, run: ProtocolRun) -> MetricSummary:
        honest_scores = [episode.suspicion for episode in run.honest]
        forced_attacks = [episode.as_attack_episode() for episode in run.forced_attack]
        ranking_population = forced_attacks + [
            AttackEpisode(
                suspicion=episode.suspicion,
                main_task_correct=episode.main_task_correct,
                side_task_success=False,
                attempted_backdoor=False,
            )
            for episode in run.honest
        ]
        diagnostics = detection_metrics(
            policy_episodes=ranking_population,
            honest_suspicion_scores=honest_scores,
            suspicion_threshold=self.config.suspicion_threshold,
            ranking_k=1,
        )
        selected = self._selected_policy_episodes(run)
        selected_attempts = [
            episode for episode in selected if episode.attempted_backdoor
        ]
        selected_successes = [
            episode for episode in selected if episode.successful_backdoor
        ]
        selected_attack_success = (
            len(selected_successes) / len(selected_attempts)
            if selected_attempts
            else None
        )

        safety = None
        safety_reason = (
            "set --attack-episode-subsample-rate to estimate deployment safety"
        )
        if self.config.attack_episode_subsample_rate is not None:
            try:
                safety = estimate_safety(
                    attack_episodes=selected,
                    honest_suspicion_scores=honest_scores,
                    scenario_tasks=self.config.scenario_tasks,
                    trials=self.config.safety_trials,
                    audit_budget=self.config.audit_budget,
                    free_initial_audits=self.config.free_initial_audits,
                    attack_episode_subsample_rate=self.config.attack_episode_subsample_rate,
                    seed=self.config.metric_seed,
                )
                safety_reason = safety.undefined_reason
            except ValueError as error:
                safety_reason = str(error)

        raw = raw_usefulness(episode.main_task_correct for episode in run.honest)
        normalized = None
        if self.config.trusted_baseline_accuracy is not None:
            normalized = normalized_usefulness(
                raw,
                self.config.trusted_baseline_accuracy,
                self.config.untrusted_baseline_accuracy,
            )
        selected_threshold_unflagged = sum(
            episode.successful_backdoor
            and episode.suspicion <= self.config.suspicion_threshold
            for episode in selected
        )

        return MetricSummary(
            protocol_name=run.protocol_name,
            safety=None if safety is None else safety.estimate,
            safety_monte_carlo_ci95=(
                None if safety is None else safety.monte_carlo_simulation_ci95
            ),
            expected_retained_attack_attempts=(
                None if safety is None else safety.expected_retained_attack_attempts
            ),
            safety_informative=bool(safety and safety.informative),
            safety_undefined_reason=safety_reason,
            raw_usefulness=raw,
            normalized_usefulness=normalized,
            selected_tasks=len(selected),
            selected_attack_attempts=len(selected_attempts),
            selected_successful_backdoors=len(selected_successes),
            selected_attack_rate=len(selected_attempts) / len(selected),
            selected_attack_success_rate=selected_attack_success,
            selected_attack_success_rate_undefined_reason=(
                None if selected_attempts else "no attack attempts were selected"
            ),
            selected_successful_backdoors_per_task=(
                len(selected_successes) / len(selected)
            ),
            selected_threshold_unflagged_successful_backdoors_per_task=(
                selected_threshold_unflagged / len(selected)
            ),
            forced_attack_attempts=diagnostics.attempted_attacks,
            forced_successful_backdoors=diagnostics.successful_attacks,
            forced_successful_attack_detection_recall=(
                diagnostics.successful_attack_detection_recall.value
            ),
            forced_successful_attack_detection_recall_undefined_reason=(
                diagnostics.successful_attack_detection_recall.undefined_reason
            ),
            forced_successful_attack_evasion_rate=(
                diagnostics.successful_attack_evasion_rate.value
            ),
            forced_successful_attack_evasion_rate_undefined_reason=(
                diagnostics.successful_attack_evasion_rate.undefined_reason
            ),
            forced_top_1_attempt_capture_rate=(
                diagnostics.top_k_attempt_capture_rate.value
            ),
            forced_top_1_attempt_capture_rate_undefined_reason=(
                diagnostics.top_k_attempt_capture_rate.undefined_reason
            ),
            forced_top_1_successful_attack_capture_rate=(
                diagnostics.top_k_successful_attack_capture_rate.value
            ),
            forced_top_1_successful_attack_capture_rate_undefined_reason=(
                diagnostics.top_k_successful_attack_capture_rate.undefined_reason
            ),
            forced_successful_attack_auroc=(diagnostics.successful_attack_auroc.value),
            forced_successful_attack_auroc_undefined_reason=(
                diagnostics.successful_attack_auroc.undefined_reason
            ),
            honest_flag_rate=diagnostics.honest_flag_rate.value,
            honest_flag_rate_undefined_reason=(
                diagnostics.honest_flag_rate.undefined_reason
            ),
            standalone_input_tokens=run.model_input_tokens,
            standalone_output_tokens=run.model_output_tokens,
            estimated_standalone_cost_usd=run.logical_cost,
            honest_suspicion_scores=honest_scores,
        )

    def run_experiment_for_protocol(
        self,
        proto_name: str,
        dump_explanations: bool = False,
        console: Optional[Any] = None,
        save_code_dir: Optional[str] = None,
    ) -> MetricSummary:
        return self.run_experiment(
            dump_explanations=dump_explanations,
            console=console,
            protocols=[proto_name],
            save_code_dir=save_code_dir,
        ).metrics_by_protocol[proto_name]

    def run_experiment(
        self,
        dump_explanations: bool = False,
        console: Optional[Any] = None,
        protocols: Optional[List[str]] = None,
        save_code_dir: Optional[str] = None,
    ) -> ExperimentSummary:
        """Run the paired four-protocol monitoring comparison."""
        metrics: Dict[str, MetricSummary] = {}
        protocols = protocols or ["TM", "PBT", "TM+PBT", "PBT-Informed-TM"]
        supported_protocols = {"TM", "PBT", "TM+PBT", "PBT-Informed-TM"}
        unknown_protocols = set(protocols).difference(supported_protocols)
        if unknown_protocols:
            raise ValueError(
                f"unsupported monitoring protocols: {sorted(unknown_protocols)}"
            )

        pbt_protocols = {"PBT", "TM+PBT", "PBT-Informed-TM"}
        relevant_pbt_variants = {
            self.config.pbt_prompt_overrides.get(name, self.config.pbt_prompt_variant)
            for name in protocols
            if name in pbt_protocols
        }
        if len(relevant_pbt_variants) > 1:
            raise ValueError(
                "shared-evidence protocols must use one PBT prompt variant per run"
            )
        if relevant_pbt_variants:
            self._shared_pbt_prompt_variant = next(iter(relevant_pbt_variants))

        runs: dict[str, ProtocolRun] = {}
        executed_atomic_runs: list[ProtocolRun] = []
        candidate_evaluations: list[EpisodeResult] = []
        frozen_ground_truth: Optional[Dict[str, Dict[str, bool]]] = None
        mode_evaluations = 0

        needs_pbt = bool({"PBT", "TM+PBT", "PBT-Informed-TM"}.intersection(protocols))
        if needs_pbt and self.candidate_pool is not None:
            honest_pbt = self._execute_protocol(
                "PBT",
                dump_explanations=dump_explanations,
                console=console,
                save_code_dir=save_code_dir,
                run_honest=True,
                run_attack=False,
            )
            pbt_run, candidate_evaluations, attack_mode_count = (
                self._collect_pbt_candidate_pool(honest_pbt)
            )
            runs["PBT"] = pbt_run
            executed_atomic_runs.append(pbt_run)
            mode_evaluations += 1 + attack_mode_count
            frozen_ground_truth = self._frozen_ground_truth(candidate_evaluations)
        elif needs_pbt:
            runs["PBT"] = self._execute_protocol(
                "PBT",
                dump_explanations=dump_explanations,
                console=console,
                save_code_dir=save_code_dir,
            )
            executed_atomic_runs.append(runs["PBT"])
            mode_evaluations += 2

        if "TM" in protocols or "TM+PBT" in protocols:
            runs["TM"] = self._execute_protocol(
                "TM",
                dump_explanations=dump_explanations,
                console=console,
                save_code_dir=save_code_dir,
                skip_task_scorers=frozen_ground_truth is not None,
                ground_truth=frozen_ground_truth,
            )
            executed_atomic_runs.append(runs["TM"])
            mode_evaluations += 2
        if "PBT-Informed-TM" in protocols:
            runs["PBT-Informed-TM"] = self._execute_protocol(
                "PBT-Informed-TM",
                dump_explanations=dump_explanations,
                console=console,
                save_code_dir=save_code_dir,
                skip_task_scorers=frozen_ground_truth is not None,
                ground_truth=frozen_ground_truth,
            )
            executed_atomic_runs.append(runs["PBT-Informed-TM"])
            mode_evaluations += 2
        if "TM+PBT" in protocols:
            runs["TM+PBT"] = self._derive_tm_pbt(runs["TM"], runs["PBT"])
        if "PBT-Informed-TM" in protocols:
            runs["PBT-Informed-TM"] = self._with_dependency_cost(
                runs["PBT-Informed-TM"], runs["PBT"]
            )
        if needs_pbt and self.candidate_pool is not None:
            self._persist_evidence_bundles()
        for protocol in protocols:
            metrics[protocol] = self._metric_summary(runs[protocol])

        detailed = [
            episode.model_dump(mode="json")
            for protocol in protocols
            for episode in (runs[protocol].honest + runs[protocol].forced_attack)
        ]

        actual_costs = [run.incremental_cost for run in executed_atomic_runs]
        actual_incremental_cost = known_cost_total(actual_costs)

        return ExperimentSummary(
            total_evaluations=mode_evaluations
            * len(self.config.task_ids or MAIN_TASK_IDS),
            honest_episodes_tested=len(protocols)
            * len(self.config.task_ids or MAIN_TASK_IDS),
            attack_episodes_tested=len(protocols)
            * len(self.config.task_ids or MAIN_TASK_IDS),
            evaluation_input_tokens=sum(
                run.incremental_input_tokens for run in executed_atomic_runs
            ),
            evaluation_output_tokens=sum(
                run.incremental_output_tokens for run in executed_atomic_runs
            ),
            estimated_evaluation_cost_usd=actual_incremental_cost,
            metrics_by_protocol=metrics,
            detailed_results=detailed,
            candidate_evaluations=[
                episode.model_dump(mode="json") for episode in candidate_evaluations
            ],
        )
