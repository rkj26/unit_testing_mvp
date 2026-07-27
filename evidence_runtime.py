"""Runtime population and persistence for shared monitor evidence."""

from __future__ import annotations

import asyncio
import fcntl
import json
import threading
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import IO, Awaitable, Callable, Mapping, Optional

from artifact_io import atomic_write_text, safe_path_component
from evidence import (
    PBT_INFORMED_TM,
    TM,
    CandidateEvidence,
    MonitorEvidence,
    PBTExecutionEvidence,
    PBTTestSuite,
    TaskEvidenceBundle,
    build_task_bundle,
    sha256_text,
)


def _json(value: object) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


@contextmanager
def _producer_manifest_lock(root: Path):
    """Serialize config compare-and-create across store instances/processes."""

    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".producer_config.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class RuntimeEvidenceStore:
    """In-process evidence registry with content-addressed on-disk artifacts.

        The registry is deliberately strict: a task has one suite, and a
        candidate/monitor-kind has one judgement within an experiment. Reusing a store
        with different producer settings raises instead of silently returning stale
        evidence. Async producer methods serialize work per key so concurrent protocol
        samples do not duplicate model calls or checker executions. A rooted store holds
    exclusive writer ownership until closed, and async production is bound to the
        same per-evidence locks across Inspect's separate event loops.
    """

    def __init__(
        self,
        root: Optional[Path | str] = None,
        *,
        producer_config: Optional[Mapping[str, object]] = None,
    ):
        self.root = Path(root).expanduser().resolve() if root is not None else None
        self._lock = threading.RLock()
        self._closed = False
        self._root_lock_handle: Optional[IO[str]] = None
        self._suites: dict[str, PBTTestSuite] = {}
        self._pbt: dict[tuple[str, str], PBTExecutionEvidence] = {}
        self._monitors: dict[tuple[str, str, str], MonitorEvidence] = {}
        self._generation_errors: dict[str, str] = {}
        self._producer_locks: dict[tuple[object, ...], asyncio.Lock] = {}
        self._active_producer_keys: set[tuple[object, ...]] = set()
        self._producer_config: Optional[dict[str, object]] = None
        self._producer_config_sha256: Optional[str] = None
        try:
            self._acquire_root_ownership()
            if producer_config is not None:
                self.bind_producer_config(producer_config)
        except Exception:
            self.close()
            raise

    def _acquire_root_ownership(self) -> None:
        """Hold an advisory writer lock for this store's entire lifetime."""

        if self.root is None:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.root / ".evidence_store.lock"
        handle = lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            handle.close()
            raise RuntimeError(
                f"evidence artifact root already has an active store: {self.root}"
            ) from error
        self._root_lock_handle = handle

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("evidence store is closed")

    def close(self) -> None:
        """Release this store's root ownership; idempotent."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            handle = self._root_lock_handle
            self._root_lock_handle = None
            if handle is not None:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()

    def __enter__(self) -> "RuntimeEvidenceStore":
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def __del__(self) -> None:
        # Best effort for callers that do not use the context-manager API.
        try:
            self.close()
        except Exception:
            pass

    @property
    def producer_config_sha256(self) -> Optional[str]:
        return self._producer_config_sha256

    def bind_producer_config(self, config: Mapping[str, object]) -> str:
        """Bind this registry/artifact root to one canonical producer config."""

        self._ensure_open()
        if not isinstance(config, Mapping):
            raise TypeError("producer config must be a mapping")
        # Round-trip to detach mutable callers and reject non-JSON/NaN values.
        normalized = json.loads(_canonical_json(dict(config)))
        digest = sha256_text(_canonical_json(normalized))
        manifest = {
            "schema_version": 1,
            "producer_config": normalized,
            "producer_config_sha256": digest,
        }
        with self._lock:
            if self._producer_config_sha256 is not None:
                if self._producer_config_sha256 != digest:
                    raise ValueError(
                        "evidence store is already bound to different producer settings"
                    )
                return digest
            if self._suites or self._pbt or self._monitors or self._generation_errors:
                raise RuntimeError(
                    "producer settings must be bound before evidence is populated"
                )
            if self.root is not None:
                with _producer_manifest_lock(self.root):
                    path = self.root / "producer_config.json"
                    if path.exists():
                        try:
                            existing = json.loads(path.read_text(encoding="utf-8"))
                        except (OSError, json.JSONDecodeError) as error:
                            raise ValueError(
                                f"invalid evidence producer config manifest: {path}"
                            ) from error
                        if existing != manifest:
                            raise ValueError(
                                "evidence artifact root belongs to different "
                                "producer settings"
                            )
                    else:
                        atomic_write_text(path, _json(manifest))
            self._producer_config = normalized
            self._producer_config_sha256 = digest
        return digest

    def _task_dir(self, task_id: str) -> Optional[Path]:
        self._ensure_open()
        if self.root is None:
            return None
        return self.root / safe_path_component(task_id, fallback="task")

    @asynccontextmanager
    async def _production_lock(self, *key: object):
        """Serialize same-loop producers and reject concurrent cross-loop use."""

        self._ensure_open()
        loop_key = (asyncio.get_running_loop(), *key)
        with self._lock:
            production_lock = self._producer_locks.setdefault(loop_key, asyncio.Lock())
        async with production_lock:
            with self._lock:
                self._ensure_open()
                if key in self._active_producer_keys:
                    raise RuntimeError(
                        "concurrent evidence production from multiple event loops "
                        "is unsupported"
                    )
                self._active_producer_keys.add(key)
            try:
                yield
            finally:
                with self._lock:
                    self._active_producer_keys.remove(key)

    @staticmethod
    def _validate_suite(
        suite: PBTTestSuite,
        *,
        task_spec_sha256: Optional[str] = None,
        prompt_sha256: Optional[str] = None,
        hypothesis_seed: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> None:
        mismatches: list[str] = []
        if task_spec_sha256 is not None and suite.task_spec_sha256 != task_spec_sha256:
            mismatches.append("task specification")
        if prompt_sha256 is not None and suite.prompt_sha256 != prompt_sha256:
            mismatches.append("rendered prompt")
        if hypothesis_seed is not None and suite.hypothesis_seed != hypothesis_seed:
            mismatches.append("Hypothesis seed")
        if model_name is not None and suite.model_name != model_name:
            mismatches.append("generator model")
        if mismatches:
            raise ValueError(
                f"shared PBT suite producer settings changed: {', '.join(mismatches)}"
            )

    def get_suite(
        self,
        task_id: str,
        *,
        task_spec_sha256: Optional[str] = None,
        prompt_sha256: Optional[str] = None,
        hypothesis_seed: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> Optional[PBTTestSuite]:
        self._ensure_open()
        with self._lock:
            suite = self._suites.get(task_id)
            if suite is not None:
                self._validate_suite(
                    suite,
                    task_spec_sha256=task_spec_sha256,
                    prompt_sha256=prompt_sha256,
                    hypothesis_seed=hypothesis_seed,
                    model_name=model_name,
                )
            return suite

    def put_suite(self, suite: PBTTestSuite) -> PBTTestSuite:
        self._ensure_open()
        with self._lock:
            existing = self._suites.get(suite.task_id)
            if existing is not None:
                if existing != suite:
                    raise ValueError(
                        f"refusing a second PBT suite for task {suite.task_id}"
                    )
                return existing
            task_dir = self._task_dir(suite.task_id)
            if task_dir is not None:
                suite_manifest = task_dir / "pbt" / "suite.json"
                # An interrupted replacement must not leave an old commit marker
                # beside partially replaced leaf files.
                suite_manifest.unlink(missing_ok=True)
                atomic_write_text(task_dir / "task_id.txt", suite.task_id + "\n")
                atomic_write_text(task_dir / "pbt" / "prompt.txt", suite.prompt)
                atomic_write_text(task_dir / "pbt" / "test.py", suite.script)
                # This manifest is the commit marker for the preceding suite files.
                atomic_write_text(suite_manifest, _json(suite.to_dict()))
                (task_dir / "pbt" / "generation_error.json").unlink(missing_ok=True)
            # Publish in memory only after all persistence operations succeed.
            self._suites[suite.task_id] = suite
            self._generation_errors.pop(suite.task_id, None)
            return suite

    async def get_or_create_suite(
        self,
        task_id: str,
        *,
        task_spec_sha256: str,
        prompt_sha256: str,
        hypothesis_seed: int,
        model_name: str,
        producer: Callable[[], Awaitable[PBTTestSuite]],
    ) -> PBTTestSuite:
        expected = {
            "task_spec_sha256": task_spec_sha256,
            "prompt_sha256": prompt_sha256,
            "hypothesis_seed": hypothesis_seed,
            "model_name": model_name,
        }
        suite = self.get_suite(task_id, **expected)
        if suite is not None:
            return suite
        async with self._production_lock("suite", task_id):
            suite = self.get_suite(task_id, **expected)
            if suite is not None:
                return suite
            prior_error = self.generation_error(task_id)
            if prior_error is not None:
                raise RuntimeError(prior_error)
            try:
                suite = await producer()
                if suite.task_id != task_id:
                    raise ValueError("PBT suite producer returned a different task")
                self._validate_suite(suite, **expected)
                return self.put_suite(suite)
            except Exception as error:
                self.record_generation_error(
                    task_id, f"{type(error).__name__}: {error}"
                )
                raise

    def record_generation_error(self, task_id: str, error: str) -> None:
        self._ensure_open()
        with self._lock:
            if task_id in self._suites:
                return
            existing = self._generation_errors.get(task_id)
            if existing is not None:
                return
            task_dir = self._task_dir(task_id)
            if task_dir is not None:
                atomic_write_text(
                    task_dir / "pbt" / "generation_error.json",
                    _json({"task_id": task_id, "error": error}),
                )
            self._generation_errors[task_id] = error

    def generation_error(self, task_id: str) -> Optional[str]:
        self._ensure_open()
        with self._lock:
            return self._generation_errors.get(task_id)

    def get_pbt(
        self,
        task_id: str,
        candidate_sha256: str,
        *,
        suite_sha256: Optional[str] = None,
    ) -> Optional[PBTExecutionEvidence]:
        self._ensure_open()
        with self._lock:
            evidence = self._pbt.get((task_id, candidate_sha256))
            if (
                evidence is not None
                and suite_sha256 is not None
                and evidence.suite_sha256 != suite_sha256
            ):
                raise ValueError("PBT execution references a different shared suite")
            return evidence

    def put_pbt(self, evidence: PBTExecutionEvidence) -> PBTExecutionEvidence:
        self._ensure_open()
        suite = self.get_suite(evidence.task_id)
        if suite is None or suite.suite_sha256 != evidence.suite_sha256:
            raise ValueError(
                "PBT execution does not reference the registered task suite"
            )
        key = (evidence.task_id, evidence.candidate_sha256)
        with self._lock:
            existing = self._pbt.get(key)
            if existing is not None:
                if existing != evidence:
                    raise ValueError(
                        "refusing conflicting PBT evidence for one candidate"
                    )
                return existing
            task_dir = self._task_dir(evidence.task_id)
            if task_dir is not None:
                atomic_write_text(
                    task_dir / "pbt" / "results" / f"{evidence.candidate_sha256}.json",
                    _json(evidence.to_dict()),
                )
            self._pbt[key] = evidence
            return evidence

    async def get_or_create_pbt(
        self,
        task_id: str,
        candidate_sha256: str,
        *,
        suite_sha256: str,
        producer: Callable[[], Awaitable[PBTExecutionEvidence]],
    ) -> PBTExecutionEvidence:
        evidence = self.get_pbt(task_id, candidate_sha256, suite_sha256=suite_sha256)
        if evidence is not None:
            return evidence
        async with self._production_lock("pbt", task_id, candidate_sha256):
            evidence = self.get_pbt(
                task_id, candidate_sha256, suite_sha256=suite_sha256
            )
            if evidence is not None:
                return evidence
            evidence = await producer()
            if (
                evidence.task_id != task_id
                or evidence.candidate_sha256 != candidate_sha256
                or evidence.suite_sha256 != suite_sha256
            ):
                raise ValueError("PBT producer returned evidence for a different key")
            return self.put_pbt(evidence)

    def get_monitor(
        self,
        task_id: str,
        candidate_sha256: str,
        kind: str,
        *,
        model_name: Optional[str] = None,
        prompt_sha256: Optional[str] = None,
    ) -> Optional[MonitorEvidence]:
        self._ensure_open()
        with self._lock:
            evidence = self._monitors.get((task_id, candidate_sha256, kind))
            if evidence is not None:
                mismatches = []
                if model_name is not None and evidence.model_name != model_name:
                    mismatches.append("model")
                if (
                    prompt_sha256 is not None
                    and evidence.prompt_sha256 != prompt_sha256
                ):
                    mismatches.append("rendered prompt")
                if mismatches:
                    raise ValueError(
                        "shared monitor producer settings changed: "
                        + ", ".join(mismatches)
                    )
            return evidence

    def put_monitor(self, evidence: MonitorEvidence) -> MonitorEvidence:
        self._ensure_open()
        key = (evidence.task_id, evidence.candidate_sha256, evidence.kind)
        with self._lock:
            existing = self._monitors.get(key)
            if existing is not None:
                if existing != evidence:
                    raise ValueError(
                        "refusing conflicting monitor evidence for one candidate"
                    )
                return existing
            task_dir = self._task_dir(evidence.task_id)
            if task_dir is not None:
                directory = "tm" if evidence.kind == TM else "informed_tm"
                atomic_write_text(
                    task_dir / directory / f"{evidence.candidate_sha256}.json",
                    _json(evidence.to_dict()),
                )
            self._monitors[key] = evidence
            return evidence

    async def get_or_create_monitor(
        self,
        task_id: str,
        candidate_sha256: str,
        kind: str,
        *,
        model_name: str,
        prompt_sha256: str,
        producer: Callable[[], Awaitable[MonitorEvidence]],
    ) -> MonitorEvidence:
        expected = {"model_name": model_name, "prompt_sha256": prompt_sha256}
        evidence = self.get_monitor(task_id, candidate_sha256, kind, **expected)
        if evidence is not None:
            return evidence
        async with self._production_lock("monitor", task_id, candidate_sha256, kind):
            evidence = self.get_monitor(task_id, candidate_sha256, kind, **expected)
            if evidence is not None:
                return evidence
            evidence = await producer()
            if (
                evidence.task_id != task_id
                or evidence.candidate_sha256 != candidate_sha256
                or evidence.kind != kind
                or evidence.model_name != model_name
                or evidence.prompt_sha256 != prompt_sha256
            ):
                raise ValueError(
                    "monitor producer returned evidence for a different key"
                )
            return self.put_monitor(evidence)

    def candidate_evidence(
        self, *, task_id: str, candidate_id: str, candidate_sha256: str
    ) -> CandidateEvidence:
        self._ensure_open()
        suite = self.get_suite(task_id)
        if suite is None:
            raise KeyError(f"missing PBT suite for {task_id}")
        pbt = self.get_pbt(task_id, candidate_sha256, suite_sha256=suite.suite_sha256)
        if pbt is None:
            raise KeyError(f"missing PBT evidence for {task_id}/{candidate_sha256}")
        return CandidateEvidence(
            task_id=task_id,
            candidate_id=candidate_id,
            candidate_sha256=candidate_sha256,
            pbt=pbt,
            tm=self.get_monitor(task_id, candidate_sha256, TM),
            informed_tm=self.get_monitor(task_id, candidate_sha256, PBT_INFORMED_TM),
        )

    def write_bundles(
        self, candidate_ids: Mapping[str, Mapping[str, str]]
    ) -> dict[str, TaskEvidenceBundle]:
        self._ensure_open()
        bundles: dict[str, TaskEvidenceBundle] = {}
        for task_id, ids_by_hash in candidate_ids.items():
            suite = self.get_suite(task_id)
            if suite is None:
                raise KeyError(f"missing PBT suite for {task_id}")
            candidates = [
                self.candidate_evidence(
                    task_id=task_id,
                    candidate_id=candidate_id,
                    candidate_sha256=candidate_hash,
                )
                for candidate_hash, candidate_id in ids_by_hash.items()
            ]
            bundle = build_task_bundle(suite, candidates)
            bundles[task_id] = bundle
            task_dir = self._task_dir(task_id)
            if task_dir is not None:
                atomic_write_text(task_dir / "bundle.json", bundle.to_json() + "\n")
        return bundles
