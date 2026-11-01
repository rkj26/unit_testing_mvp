# Completed Grok generated solutions

This addendum publishes all 1,724 existing nonfailed TrustedSolve generated solution records from the saved partial Grok run, including records with `solves=false`. No fresh generation, inference, recovery, candidate execution, or regrading was performed.

These are specification-generated solutions, not the original honest/attack dataset candidates. `label` and `is_attack` refer to the associated original dataset record and do not classify the generated solution as malicious. Both original candidate identities for a task can have separately generated solutions; these are not independent task replications.

[completed-generated-solutions.jsonl](completed-generated-solutions.jsonl) preserves the exact native `solution` strings, stable identities, split, failure flag, and `solves` outcomes. [provenance.json](provenance.json) gives whole-source/output hashes and documents per-row/code hashes. Source row order is preserved, with a zero-based source index. The one failed row remains in the existing outcome release and full local evidence. Pending/unattempted candidates are not included.

No calls, prompts, raw replies/reasoning, original dataset candidate code, or dataset input payloads are included. Generated code has not been executed for publication and should be treated as untrusted; do not automatically execute it. This addendum is a static code-and-outcome archive, not a resumable run or authority to start inference.
