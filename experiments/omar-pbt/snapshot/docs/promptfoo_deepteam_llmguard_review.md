# promptfoo, DeepTeam and LLM Guard: source-level PBT fit review

Reviewed 2026-09-06. The intended library is **promptfoo, not Promptify**. This is a bounded review of the implementations listed below, not an exhaustive claim that these repositories contain no other useful testing material. No framework was installed, no model was called, and no experimental prompt was changed by this review.

## Decision

Use these projects as sources of design patterns, not as drop-in property-based-test generators or proof that a software-testing standard improves detection. promptfoo supplies configurable assertions and model-grading prompts; DeepTeam provides security-evaluation prompts; LLM Guard provides executable scanners. None of the inspected implementations establishes whether a generated Python assertion is true for every correct solution to an APPS task.

**Keep the current `plain_v3` versus `traceable_v1` comparison unchanged.** No new PBT-writing template is sufficiently justified by this review. Do not add a framework dependency or replace execution outcomes with an LLM grader. The smoke test independently motivated input-domain checks and duplicate-test diagnostics; deterministic assertions in promptfoo are consistent with that approach, but these checks are not newly borrowed innovations. Explicit protection against embedded instructions is a separate future intervention, not an unmeasured improvement to slip into the current arm.

## Pinned primary sources

The commit IDs below were resolved through GitHub's public commits API; source files were fetched directly from `raw.githubusercontent.com` at those commits.

- DeepTeam: `dc148aad62f71330cfec7121d6afb4c620dfa683`.
- LLM Guard: `168c1034ffdb33837e7ae6fd6a16b80567c1be03`.
- promptfoo: `6d0395a20520e19cf8889d572b879ec9c2831a52`.

### promptfoo

1. [`DEFAULT_GRADING_PROMPT` and `DEFAULT_AGENT_GRADING_PROMPT`](https://github.com/promptfoo/promptfoo/blob/6d0395a20520e19cf8889d572b879ec9c2831a52/src/prompts/grading.ts) produce a reason, Boolean pass, and numerical score against a supplied rubric. The agent-grading variant explicitly treats evaluated output and retrieved material as untrusted evidence, with restrictions on actions. These are public grading prompts, not prompts that author executable APPS properties.

2. [`Python assertion handler`](https://github.com/promptfoo/promptfoo/blob/6d0395a20520e19cf8889d572b879ec9c2831a52/src/assertions/python.ts) supports custom Python evaluation. Its exception handler returns a failed result with score zero and an execution-error reason. That is a valid application-testing convention but does not match this research pipeline's rule that measurement errors leave the success-rate denominator. Porting its aggregation unchanged would conflate failed measurement with measured model failure.

3. [`LLM rubric assertion`](https://github.com/promptfoo/promptfoo/blob/6d0395a20520e19cf8889d572b879ec9c2831a52/src/assertions/llmRubric.ts) and [`rubric matcher`](https://github.com/promptfoo/promptfoo/blob/6d0395a20520e19cf8889d572b879ec9c2831a52/src/matchers/rubric.ts) provide configurable model judging. This is useful infrastructure when the evaluation target is a rubric, but a model's judgment cannot replace execution-based evidence of a valid assertion failure in the present experiment.

### DeepTeam

1. [`CodeScanTemplate.generate_code_batch_evaluation`](https://github.com/confident-ai/deepteam/blob/dc148aad62f71330cfec7121d6afb4c620dfa683/deepteam/code_scanner/template.py) constructs a static AI-application security review prompt. Its output requires a recognized vulnerability category/type, file and absolute line locations, explanation, recommendation, and code evidence. An empty findings list is explicitly allowed. This is evidence-linked static review, not executable PBT authoring.

2. [`render_judge_scope_block` and calibration blocks](https://github.com/confident-ai/deepteam/blob/dc148aad62f71330cfec7121d6afb4c620dfa683/deepteam/metrics/evaluation_prompt_blocks.py) limit a judge to the requested subtype and append domain guidance and examples. The transferable idea is to avoid failures on unrelated dimensions. However, these examples are prompt calibration, not held-out statistical FPR calibration; copying that terminology would conflate different procedures.

3. [`VerificationAssessmentTemplate`](https://github.com/confident-ai/deepteam/blob/dc148aad62f71330cfec7121d6afb4c620dfa683/deepteam/metrics/agentic/verification_assessment/template.py) supplies a natural-language rubric concerning validation, contradiction, uncertainty, and verification bypass. At the inspected commit its opening and final instructions identify 0 as vulnerable and 1 as secure, but an intermediate failure-analysis instruction labels 1 vulnerable. This inconsistency is visible in source; the prompt should not be copied without repair and regression tests.

4. [`HierarchyConsistencyTemplate`](https://github.com/confident-ai/deepteam/blob/dc148aad62f71330cfec7121d6afb4c620dfa683/deepteam/metrics/agentic/hierarchy_consistency/template.py) asks whether lower-level objectives override higher-level ones and requests concrete evidence. It too has inconsistent score wording: opening/final mapping gives 1 for secure behavior, while an intermediate instruction assigns secure behavior 0. Retain the trust-boundary idea, not this scoring contract.

### LLM Guard

1. [`JSON.scan`](https://github.com/protectai/llm-guard/blob/168c1034ffdb33837e7ae6fd6a16b80567c1be03/llm_guard/output_scanners/json.py) locates candidate JSON fragments, parses them, and optionally repairs them. The actual constructor defaults are `required_elements=0` and `repair=True`. Empty output returns valid immediately; nonempty text containing no candidate JSON can also pass at the default minimum. It does not validate our required rationale/tests schema or Python function semantics. Automatic repair changes the measured answer and must not be silently introduced into the experiment.

2. [`PromptInjection.scan`](https://github.com/protectai/llm-guard/blob/168c1034ffdb33837e7ae6fd6a16b80567c1be03/llm_guard/input_scanners/prompt_injection.py) runs a Hugging Face classification model, converts its class probability to an injection score, and compares it with a configured threshold. The source uses a pinned DeBERTa model revision, not a reusable unit-test-writing system prompt. A classifier for prompt injection is not a validator of Python input domains or correct output properties. Filtering benchmark submissions through it would introduce a separate selection intervention requiring its own evaluation.

3. [`Secrets.scan`](https://github.com/protectai/llm-guard/blob/168c1034ffdb33837e7ae6fd6a16b80567c1be03/llm_guard/input_scanners/secrets.py) delegates secret detection to `detect-secrets`, then produces sanitized text and a validity/risk result. It is relevant to credential hygiene, not test correctness. Do not silently redact benchmark literals before scoring: that can change the candidate or its trigger. A separate prepublication artifact check is the appropriate place to consider this functionality.

## Comparison with the current pipeline

| Candidate pattern | Already present | Incremental decision |
|---|---|---|
| Link each assertion to evidence | `framing_plain_v3.txt` already requires specification justification; `framing_traceable_v1.txt` explicitly records requirement, technique, oracle, and validity | Retain; do not claim this was absent before the review |
| Scope a verdict to the actual target | Baseline forbids implementation-derived correctness claims; traceability adds an explicit review | Preserve current prompts; any embedded-instruction defense belongs in a separate experiment |
| Typed/structured output | `tests_schema` is sent to the provider; `suite_source` parses the answer; sandbox records execution outcomes | Do not replace with permissive JSON scanning or invisible repair |
| Evidence from execution | Docker harness distinguishes assertion catches, passes, candidate crashes, and test errors | Retain as the measurement; a natural-language judge must not substitute for it |
| Secret handling | Credentials are configured separately and must remain outside prompts/artifacts | Consider publication hygiene separately, not as a PBT treatment |

Local comparison sources: `prompts/framing_plain_v3.txt`, `prompts/framing_traceable_v1.txt`, and `pipeline/protocols/unit_testing.py` (`tests_schema`, `suite_source`, `_prompt`, `suite_verdict`).

## Concrete next steps

1. Preserve the existing prompt ablation and shared trigger inputs.
2. Validate input domains before interpreting catches; distinguish invalid inputs from model detection failures.
3. Report the number of structurally distinct tests rather than treating repeated functions as independent evidence. Track vacuous or guarded checks where possible; a passing execution alone does not prove an assertion ran.
4. Retain strict response parsing and separate infrastructure/test errors from measured catches and honest false alarms.
5. Keep prompt-injection hardening, secret scanning, and LLM-rubric grading outside the primary intervention unless separately designed and labeled.

## What this review does not establish

It does not establish that promptfoo, DeepTeam, or LLM Guard improves PBT false-positive rate or attack detection. It does not certify compliance with ISO/IEEE software-testing standards. It does not justify importing a framework merely because it offers public prompts. The value of any later adaptation must be measured against the unchanged baseline using shared inputs, honest controls, and explicit error accounting.
