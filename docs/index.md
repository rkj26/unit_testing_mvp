# probe & audit

Two halves of one experiment, split by whether they cost money.

| | |
|---|---|
| **`probe`** | runs an arm: writes tests, executes them, stores the result. Model calls, docker, hours. |
| **`audit`** | reads a finished run. No model calls, no execution, instant. What the notebooks use. |

Nothing in `audit` can change a result, and nothing in `probe` is needed to read one.

```{toctree}
:maxdepth: 2

guide
pipeline
api
```
