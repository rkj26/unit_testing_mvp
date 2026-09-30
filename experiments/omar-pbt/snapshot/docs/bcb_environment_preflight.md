# BigCodeBench PBT environment preflight

This is a static dependency and fixture inventory for the 26 tasks in `data/bcb.json`. Candidate and reference source was parsed with Python `ast`; no candidate code was executed and no network or Docker call was made.

## Observed imports

The third-party import set is:

- `numpy` (tasks 121, 141, 149, 150, 33, 61, 84, 86)
- `pandas` (121, 141, 149, 150, 151, 153, 50, 52, 54, 55, 63, 64, 65, 66, 84, 86, 87, 95, 9)
- `scikit-learn` (`sklearn`, 151, 153, 54)
- `matplotlib` (50, 61, 63, 64, 65, 9)
- `seaborn` (64, 66, 9)
- `regex` (52, 54)
- `pytz` (50)

The remaining imports are Python standard library modules: `base64`, `collections`, `datetime`, `functools`, `ipaddress`, `itertools`, `json`, `math`, `random`, `re`, `socket`, `statistics`, `threading`, and `zlib`.

Local `.venv` versions used for the pinned top-level requirements are numpy 2.5.2, pandas 3.0.5, scikit-learn 1.9.0, matplotlib 3.11.1, seaborn 0.13.2, and regex 2026.9.3. `pytz` is imported by task 50 but is not installed in the local environment; the Docker requirements pin 2025.2 and must be verified at image build time.

## Fixture and execution limits

All 26 task specifications have empty `provided_inputs` and `provided_outputs`; input generation or a separate fixture bundle is therefore required before measurement. The dataset contains 10 training and 16 test task IDs, with one honest and one attack candidate per task. Labels are inherited from pool construction.

Task `BigCodeBench/147` is a real environment boundary: both candidates scan a CIDR range using TCP sockets and threads. It remains in the study population, but the existing sandbox is network-disabled, so the measurement cannot represent external service/host reachability. Treat connection refusal or timeout as environment-limited coverage, not as a general negative about the candidate. A future explicitly controlled loopback listener would change the tested environment and must be declared; no such fixture is added by this preflight.

No other task source contains observed file-opening, HTTP client, database, or external-service calls in the specification/reference/candidate AST inventory. Many tasks return pandas DataFrames, matplotlib Axes, or plots. The harness JSON-decodes only the input fixture; candidate returns remain native Python objects inside the test process, so model-written tests can assert directly on DataFrames, Axes, and plot properties. The fixture requirement is therefore JSON-serializable argument mappings, not JSON serialization of every return value. Tasks 121, 141, 149, 150, 151, 153, 50, 61, 63, 64, 65, 66, 84, 86, and 9 still need tests that define meaningful object-level invariants rather than relying on generic equality.

The image in [`docker/bcb-pbt/Dockerfile`](../docker/bcb-pbt/Dockerfile) is based on the repository's pinned Python 3.12 slim digest and sets `MPLBACKEND=Agg` for headless plotting. Installing requirements needs network access during image build; candidate execution must still use the existing runtime's network isolation and resource/time limits.

## Recheck before measurement

1. Build the image and verify all imports, including the uninstalled `pytz` pin.
2. Generate and freeze JSON-serializable task-specific inputs; record which native DataFrame, Axes, plot, dictionary, or other return invariants each test asserts.
3. Keep task 147 in the population and report its external-network limitation explicitly; do not interpret blocked external sockets as a clean behavioral negative or silently drop the task.
4. Keep generated inputs and fixture hashes beside the run manifest; do not execute candidate code on the host.
