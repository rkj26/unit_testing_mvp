API reference
=============

Generated from the docstrings in the source, so it cannot drift from the code.

``pipeline.data`` — the dataset, its split, and what a prompt may see
---------------------------------------------------------------------

``Task.blind()`` returns exactly the fields a prompt may contain — ``entry_point``,
``io_mode``, ``main_task``, ``provided_tests`` — so a protocol that renders a prompt
cannot reach ``reference_solution`` or ``secret_input`` by accident.

.. automodule:: pipeline.data
   :members:

``pipeline.protocols.base`` — ``Run``, the spine every protocol shares
-----------------------------------------------------------------------

A run serialises itself to ``runs/<run_name>/config.json`` and the subprocess rebuilds
the same class out of that file. ``probe.json`` carried no self-describing config, so an
arm's meaning lived in a dict in whichever script happened to read it, and those dicts
drifted until three published premises were wrong.

.. automodule:: pipeline.protocols.base
   :members:

``pipeline.protocols.tm`` — the trusted monitor
-------------------------------------------------

.. automodule:: pipeline.protocols.tm
   :members:

``pipeline.protocols.trigger_search`` — the inputs a suite is later run over
-----------------------------------------------------------------------------

.. automodule:: pipeline.protocols.trigger_search
   :members:

``pipeline.protocols.unit_testing`` — one suite against one submission
------------------------------------------------------------------------

.. automodule:: pipeline.protocols.unit_testing
   :members:

``pipeline.model`` — one runtime in, one completion out
---------------------------------------------------------

.. automodule:: pipeline.model
   :members:

``pipeline.prompts`` — rendering
----------------------------------

.. automodule:: pipeline.prompts
   :members:

``pipeline.parse`` — reading one completion
---------------------------------------------

.. automodule:: pipeline.parse
   :members:

``pipeline.sandbox`` — the sandbox
------------------------------------

The only place untrusted candidate code runs. A firing test is ``outcome == "catch"``;
there is no ``"fail"``, and filtering for one scores every suite clean.

.. automodule:: pipeline.sandbox
   :members:

``pipeline.launch`` — starting a run detached
-----------------------------------------------

.. automodule:: pipeline.launch
   :members:
