"""GEPA reflective prompt optimization for the blind-PBT property generator.

Optimizes `prompts/property_gen.txt` against the same soundness-gated catch signal the pipeline
already computes in `pipeline.pbt.evaluate`. The search space is frozen per task so the property
prompt is the only thing that varies (one change per experiment, per CLAUDE.md).
"""
