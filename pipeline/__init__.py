"""Step-wise, benchmark-agnostic PBT-vs-TM control pipeline.

Config -> Preprocess -> [ Generate PBT -> Generate trigger search space -> Score PBT
-> Run TM -> max(PBT,TM) -> PBT-informed TM -> Metrics ] x N runs -> Compile results.

See README.md for the design. The benchmark-specific pieces live in
``pipeline.backends`` behind the ``Backend`` protocol in ``pipeline.schema``; everything
else is domain-agnostic.
"""
