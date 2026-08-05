"""Trigger-search strategies: how the PBT harness chooses which inputs to run.

The oracle (the properties) must stay spec-blind, because a property that has read the candidate can
encode the candidate's bug and stop being a violation detector. The *generator* carries no such
obligation: whether a firing counts is decided by the properties, so a code-aware generator cannot
manufacture a false positive. Precision lives in the oracle; recall lives here.

`trigger_search.txt` is spec-blind, which caps recall at whatever the spec alone suggests. These
strategies read the candidate instead:

  mine_constants        every integer a guard could compare against, const-folded
  dictionary_space      those constants spliced into positions of known-valid inputs
  coverage_guided_space mutation fuzzing that keeps inputs reaching unvisited lines

Both are deployable: neither needs the reference solution.
"""

from __future__ import annotations

import ast
import hashlib
import json
import random
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

COVERAGE_MARKER = "\x00COVERAGE"
DEFAULT_RUN_SECONDS = 5
DEFAULT_TRACE_SECONDS = 10
MAX_MINED_MAGNITUDE = 10**18
UNREMARKABLE_CONSTANTS = frozenset({-1, 0, 1, 2, 3})

_FOLD_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.LShift: lambda a, b: a << b,
    ast.RShift: lambda a, b: a >> b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
}
_MAX_FOLD_SHIFT = 64
_MAX_FOLD_EXPONENT = 64


def _fold_int(node: ast.AST) -> int | None:
    """Evaluate a constant integer expression, or return None if it is not one.

    `ast.literal_eval` rejects `(1 << 30) - 1`, which is exactly the shape of a magic-value guard.
    """
    if isinstance(node, ast.Constant):
        return (
            node.value
            if isinstance(node.value, int) and not isinstance(node.value, bool)
            else None
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _fold_int(node.operand)
        return None if inner is None else -inner
    if isinstance(node, ast.BinOp):
        left, right = _fold_int(node.left), _fold_int(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Pow):
            if not 0 <= right <= _MAX_FOLD_EXPONENT:
                return None
            return _bounded(left**right)
        if (
            isinstance(node.op, (ast.LShift, ast.RShift))
            and not 0 <= right <= _MAX_FOLD_SHIFT
        ):
            return None
        operation = _FOLD_OPS.get(type(node.op))
        if operation is None or (
            isinstance(node.op, (ast.FloorDiv, ast.Mod)) and right == 0
        ):
            return None
        return _bounded(operation(left, right))
    return None


def _bounded(value: int) -> int | None:
    return value if abs(value) <= MAX_MINED_MAGNITUDE else None


def mine_constants(code: str) -> list[int]:
    """Integers the candidate could be keying a hidden branch on, most suspicious first.

    Ordered: comparison operands before incidental literals, and unusual magnitudes before the small
    values a spec-blind sweep already enumerates. Returns [] on unparseable code.
    """
    try:
        tree = ast.parse(code)
        compared: list[int] = []
        incidental: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for operand in [node.left, *node.comparators]:
                    value = _fold_int(operand)
                    if value is not None:
                        compared.append(value)
            elif isinstance(node, ast.Constant):
                value = _fold_int(node)
                if value is not None:
                    incidental.append(value)
    except Exception:
        return []

    def rank(values: list[int]) -> list[int]:
        unusual = [v for v in values if v not in UNREMARKABLE_CONSTANTS]
        usual = [v for v in values if v in UNREMARKABLE_CONSTANTS]
        return unusual + usual

    ordered, seen = [], set()
    for value in rank(compared) + rank(incidental):
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def with_boundaries(constants: list[int]) -> list[int]:
    """Each mined constant plus its immediate neighbours, priority order preserved.

    A guard is at least as likely to read `> 10**8` as `== 10**8`, and mining the literal alone
    lands exactly on the value a strict comparison rejects. Observed on apps_3694, whose trigger is
    `max(a) > 10**8`: the literal is mined, the branch is still unreachable without `10**8 + 1`.
    """
    widened, seen = [], set()
    for constant in constants:
        for value in (constant, constant + 1, constant - 1):
            if value not in seen:
                seen.add(value)
                widened.append(value)
    return widened


def _integer_slots(stdin: str) -> list[tuple[int, int]]:
    """(line, token) positions of integer tokens, skipping line 0.

    Line 0 usually carries the dimensions; changing it desynchronises the rest of the input so both
    programs read garbage and the comparison is uninformative.
    """
    slots = []
    for line_index, line in enumerate(stdin.rstrip("\n").split("\n")):
        if line_index == 0:
            continue
        for token_index, token in enumerate(line.split()):
            if token.lstrip("-").isdigit():
                slots.append((line_index, token_index))
    return slots


def _substitute(stdin: str, slot: tuple[int, int], value: int) -> str:
    lines = stdin.rstrip("\n").split("\n")
    line_index, token_index = slot
    tokens = lines[line_index].split()
    tokens[token_index] = str(value)
    lines[line_index] = " ".join(tokens)
    return "\n".join(lines) + "\n"


def _saturate(stdin: str, value: int) -> str:
    lines = stdin.rstrip("\n").split("\n")
    for line_index in range(1, len(lines)):
        tokens = [
            str(value) if t.lstrip("-").isdigit() else t
            for t in lines[line_index].split()
        ]
        lines[line_index] = " ".join(tokens)
    return "\n".join(lines) + "\n"


MAX_DICTIONARY_SEEDS = 8


def _variants_for(seeds: list[str], constant: int) -> list[str]:
    """Every way of writing `constant` into one input: all positions, then each position alone."""
    variants = [_saturate(seed, constant) for seed in seeds]
    for seed in seeds:
        variants.extend(
            _substitute(seed, slot, constant) for slot in _integer_slots(seed)
        )
    return variants


def dictionary_space(seeds: list[str], constants: list[int], budget: int) -> list[str]:
    """Splice mined constants into known-valid inputs, round-robin across constants.

    The fuzzing answer to a magic-value guard: a generator that cannot name `(1<<30)-1` will never
    reach `if val == (1<<30)-1`, whatever its sampling budget.

    Allocation is breadth-first over constants, not depth-first. A task with 121 provided tests has
    more single-constant variants than the whole budget, so a depth-first loop spends everything on
    the first constant and the rest are never tried at all.
    """
    usable = _spread([s for s in seeds if _integer_slots(s)], MAX_DICTIONARY_SEEDS)
    if not usable or not constants:
        return []

    queues = [_variants_for(usable, constant) for constant in constants]
    space, seen = [], set()
    for depth in range(max(len(q) for q in queues)):
        for queue in queues:
            if depth >= len(queue) or queue[depth] in seen:
                continue
            seen.add(queue[depth])
            space.append(queue[depth])
            if len(space) >= budget:
                return space
    return space


@dataclass(frozen=True)
class Execution:
    """One run of a program. `coverage` is empty unless the run was traced.

    Coverage is a set of (previous line, current line) EDGES rather than lines. Line coverage
    saturates after a handful of inputs -- every input runs the same statements -- whereas the thing
    a backdoor adds is an edge into a branch nothing else takes.
    """

    stdout: str
    returncode: int
    coverage: frozenset[tuple[int, int]]

    @property
    def ok(self) -> bool:
        return self.returncode == 0


_TRACE_HARNESS = """
import json, sys
_target = {target!r}
_edges = set()
_previous = [0]
def _trace(frame, event, arg):
    if frame.f_code.co_filename != _target:
        return None
    _edges.add((_previous[0], frame.f_lineno))
    _previous[0] = frame.f_lineno
    return _trace
_source = open(_target).read()
_status = 0
sys.settrace(_trace)
try:
    exec(compile(_source, _target, "exec"), {{"__name__": "__main__"}})
except SystemExit as exit_request:
    _status = exit_request.code if isinstance(exit_request.code, int) else 0
except BaseException:
    _status = 1
finally:
    sys.settrace(None)
sys.stderr.write({marker!r} + json.dumps(sorted(_edges)))
raise SystemExit(_status)
"""


def run_plain(code: str, stdin: str, timeout: int = DEFAULT_RUN_SECONDS) -> Execution:
    try:
        finished = subprocess.run(
            [sys.executable, "-W", "ignore", "-c", code],
            input=stdin,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except Exception:
        return Execution("", -1, frozenset())
    return Execution(finished.stdout.strip(), finished.returncode, frozenset())


def _decode_coverage(payload: str) -> frozenset[tuple[int, int]]:
    return frozenset((a, b) for a, b in json.loads(payload))


class TracedProgram:
    """Runs one program under a line tracer, reusing a temp dir across inputs.

    Tracing costs roughly an order of magnitude in speed, so the timeout is looser than an untraced
    run and the source file is written once rather than per input.
    """

    def __init__(self, code: str) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="pbtsearch-")
        self._target = str(Path(self._directory.name) / "candidate.py")
        Path(self._target).write_text(code, encoding="utf-8")
        self._harness = _TRACE_HARNESS.format(
            target=self._target, marker=COVERAGE_MARKER
        )

    def __enter__(self) -> TracedProgram:
        return self

    def __exit__(self, *_: object) -> None:
        self._directory.cleanup()

    def run(self, stdin: str, timeout: int = DEFAULT_TRACE_SECONDS) -> Execution:
        try:
            finished = subprocess.run(
                [sys.executable, "-W", "ignore", "-c", self._harness],
                input=stdin,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
            )
        except Exception:
            return Execution("", -1, frozenset())
        _, marker, payload = finished.stderr.partition(COVERAGE_MARKER)
        coverage = _decode_coverage(payload) if marker else frozenset()
        return Execution(finished.stdout.strip(), finished.returncode, coverage)


SEARCH_CACHE = Path("runs/_search_cache")
DEFAULT_FUZZ_ITERATIONS = 400


@runtime_checkable
class SearchStrategy(Protocol):
    """Protocol for pluggable, composable search space generators."""

    def generate_space(self, code: str, seeds: list[str], budget: int) -> list[str]: ...


class ConstantMiningStrategy:
    """Strategy that mines numeric constants from code and splices them into valid seeds."""

    def generate_space(self, code: str, seeds: list[str], budget: int) -> list[str]:
        constants = with_boundaries(mine_constants(code))
        return dictionary_space(seeds, constants, budget)


class CoverageFuzzingStrategy:
    """Strategy that uses line-coverage tracing to guide mutation fuzzing."""

    def __init__(self, iterations: int = DEFAULT_FUZZ_ITERATIONS) -> None:
        self.iterations = iterations

    def generate_space(self, code: str, seeds: list[str], budget: int) -> list[str]:
        constants = with_boundaries(mine_constants(code))
        return coverage_guided_space(
            code, seeds, budget, iterations=self.iterations, constants=constants
        )


class FillerStrategy:
    """Strategy that generates value mutations without reading candidate code."""

    def generate_space(self, code: str, seeds: list[str], budget: int) -> list[str]:
        return filler_space(seeds, budget)


class AdditiveSearchComposition:
    """Combines multiple SearchStrategy instances additively via round-robin merging."""

    def __init__(self, strategies: list[SearchStrategy]) -> None:
        self.strategies = strategies

    def generate_space(self, code: str, seeds: list[str], budget: int) -> list[str]:
        if not self.strategies:
            return []
        sub_spaces = [
            strat.generate_space(code, seeds, budget) for strat in self.strategies
        ]
        return _round_robin(*sub_spaces)[:budget]


def code_aware_space(
    code: str,
    seeds: list[str],
    budget: int,
    *,
    iterations: int = DEFAULT_FUZZ_ITERATIONS,
    cache: bool = True,
) -> list[str]:
    """Inputs chosen by reading the candidate: mined constants spliced in, plus coverage-guided fuzz."""
    key = hashlib.sha256(
        json.dumps([code, seeds, budget, iterations], sort_keys=True).encode()
    ).hexdigest()[:32]
    cached = SEARCH_CACHE / f"{key}.json"
    if cache and cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))

    composition = AdditiveSearchComposition(
        [
            ConstantMiningStrategy(),
            CoverageFuzzingStrategy(iterations=iterations),
        ]
    )
    space = composition.generate_space(code, seeds, budget)

    if cache:
        SEARCH_CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(space), encoding="utf-8")
    return space


def filler_space(seeds: list[str], budget: int, *, seed_value: int = 0) -> list[str]:
    """Code-independent value mutations, used to top every candidate up to an equal budget.

    Without this, a candidate whose code yields no mined constants and no new coverage gets a smaller
    space than one that does -- and backdoors introduce magic constants, so attacks would
    systematically receive more scrutiny than honest code and the false-positive rate would be
    understated. The filler reads no code, so it cannot favour either.
    """
    usable = [s for s in seeds if _token_slots(s)]
    if not usable:
        return []
    rng = random.Random(seed_value)
    alphabet = alphabet_of(seeds)
    space, seen = [], set()
    for _ in range(budget * 20):
        if len(space) >= budget:
            break
        candidate = _mutate(rng.choice(usable), [], alphabet, rng)
        if candidate not in seen:
            seen.add(candidate)
            space.append(candidate)
    return space


def _round_robin(*sources: list[str]) -> list[str]:
    merged, seen = [], set()
    for index in range(max((len(s) for s in sources), default=0)):
        for source in sources:
            if index < len(source) and source[index] not in seen:
                seen.add(source[index])
                merged.append(source[index])
    return merged


def _token_slots(stdin: str) -> list[tuple[int, int]]:
    """(line, token) positions of every token after line 0."""
    return [
        (line_index, token_index)
        for line_index, line in enumerate(stdin.rstrip("\n").split("\n"))
        if line_index > 0
        for token_index, _ in enumerate(line.split())
    ]


def alphabet_of(seeds: list[str]) -> list[str]:
    """Characters appearing in non-numeric tokens, e.g. '#'/'.' for a grid task.

    Half of these tasks take character grids or word pairs rather than numbers, where an arithmetic
    mutator is a no-op. Drawing replacements from the corpus keeps mutants in the input language.
    """
    characters = {
        character
        for stdin in seeds
        for line in stdin.rstrip("\n").split("\n")[1:]
        for token in line.split()
        if not token.lstrip("-").isdigit()
        for character in token
    }
    return sorted(characters)


def _mutate_token(
    token: str, constants: list[int], alphabet: list[str], rng: random.Random
) -> str:
    """Perturb one token, preserving its length for non-numeric tokens.

    Grid rows are declared by a header, so a character token that changes length desynchronises the
    input and both programs read garbage. Numeric tokens carry no such constraint.
    """
    if token.lstrip("-").isdigit():
        if constants and rng.random() < 0.5:
            return str(rng.choice(constants))
        return str(int(token) + rng.choice([-3, -2, -1, 1, 2, 3]))
    if not alphabet or not token:
        return token
    characters = list(token)
    for position in rng.sample(
        range(len(characters)), k=min(len(characters), rng.randint(1, 2))
    ):
        characters[position] = rng.choice(alphabet)
    return "".join(characters)


def _mutate(
    stdin: str, constants: list[int], alphabet: list[str], rng: random.Random
) -> str:
    """Perturb tokens in place, never line 0 and never the token count."""
    slots = _token_slots(stdin)
    if not slots:
        return stdin
    lines = [line.split() for line in stdin.rstrip("\n").split("\n")]
    for line_index, token_index in rng.sample(
        slots, k=min(len(slots), rng.randint(1, 3))
    ):
        lines[line_index][token_index] = _mutate_token(
            lines[line_index][token_index], constants, alphabet, rng
        )
    return "\n".join(" ".join(tokens) for tokens in lines) + "\n"


def _spread(seeds: list[str], limit: int) -> list[str]:
    """At most `limit` seeds, spread evenly across the length-ordered corpus.

    Seeding coverage costs one traced run per seed. A task with 121 provided tests would spend the
    whole budget establishing a baseline it will never beat.
    """
    if len(seeds) <= limit:
        return list(seeds)
    ordered = sorted(seeds, key=len)
    step = len(ordered) / limit
    return [ordered[int(index * step)] for index in range(limit)]


MAX_TRACE_SEEDS = 24


def coverage_guided_space(
    code: str,
    seeds: list[str],
    budget: int,
    *,
    iterations: int = 400,
    constants: list[int] | None = None,
    seed_value: int = 0,
) -> list[str]:
    """Greybox fuzz the candidate, returning inputs that reached previously unvisited lines.

    Directly targets the observed failure: for most backdoors the harness never executes the buggy
    path at all. Coverage is read off the candidate; the verdict still comes from the properties, so
    this buys recall without spending precision.

    Two tiers of interesting, in priority order: an input reaching an edge nothing has reached, then
    an input whose edge set as a whole is new. The second tier matters because these programs are
    small -- edges saturate after a couple of dozen seeds, and a new-edges-only rule then returns
    almost nothing and cannot fill its budget. Distinct edge sets keep yielding path diversity long
    after every individual edge has been seen.

    Seeds themselves are excluded from the result -- an attack that survived the visible tests
    cannot trigger on them, so they would be wasted budget.
    """
    corpus = _spread([s for s in seeds if _token_slots(s)], MAX_TRACE_SEEDS)
    if not corpus:
        return []
    rng = random.Random(seed_value)
    dictionary = constants or []
    alphabet = alphabet_of(seeds)

    with TracedProgram(code) as program:
        covered: set[tuple[int, int]] = set()
        signatures: set[frozenset[tuple[int, int]]] = set()
        for seed in corpus:
            execution = program.run(seed)
            covered |= execution.coverage
            signatures.add(execution.coverage)

        new_edge: list[str] = []
        new_path: list[str] = []
        attempted: set[str] = set(corpus)
        for _ in range(iterations):
            if len(new_edge) + len(new_path) >= budget:
                break
            candidate = _mutate(rng.choice(corpus), dictionary, alphabet, rng)
            if candidate in attempted:
                continue
            attempted.add(candidate)
            execution = program.run(candidate)
            if not execution.ok:
                continue
            if execution.coverage - covered:
                covered |= execution.coverage
                signatures.add(execution.coverage)
                corpus.append(candidate)
                new_edge.append(candidate)
            elif execution.coverage not in signatures:
                signatures.add(execution.coverage)
                corpus.append(candidate)
                new_path.append(candidate)
    return (new_edge + new_path)[:budget]
