API reference
=============

Generated from the docstrings in the source, so it cannot drift from the code.

``audit`` — reading a finished run
----------------------------------

.. automodule:: audit
   :members:
   :undoc-members:

``probe`` — running an arm
--------------------------

.. automodule:: probe
   :members:
   :exclude-members: main

``analyse_probes`` — held-out metrics
-------------------------------------

.. automodule:: analyse_probes
   :members:
   :exclude-members: main

``deployment_game`` — block-then-audit simulation
-------------------------------------------------

.. automodule:: deployment_game
   :members:
   :exclude-members: main

``pipeline.launch`` — starting a run detached
---------------------------------------------

.. automodule:: pipeline.launch
   :members:

``pipeline.schema`` — the shared records
----------------------------------------

.. automodule:: pipeline.schema
   :members:

``pipeline.outcome`` — how this repo says "we don't know"
----------------------------------------------------------

.. automodule:: pipeline.outcome
   :members:

``pipeline.harness`` — the sandbox
-----------------------------------

.. automodule:: pipeline.harness
   :members: run_raw, build_harness, Isolation

``pipeline.pbt`` — rendering and parsing
-----------------------------------------

.. automodule:: pipeline.pbt
   :members: render, parse_properties, parse_search_space, read_input_lines, input_block, wrong_shape

``pipeline.monitor`` — the trusted monitor
-------------------------------------------

.. automodule:: pipeline.monitor
   :members:

``pipeline.metrics`` — the deployment game
--------------------------------------------

.. automodule:: pipeline.metrics
   :members: MetricConfig, AuditRule, stat, safety
