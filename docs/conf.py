"""Sphinx configuration. Build with `.venv/bin/python -m sphinx docs docs/_build/html`."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

project = "probe & audit"
author = "unit_testing_mvp"
extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx.ext.viewcode", "myst_parser"]

# probe.py imports the model stack; autodoc only needs the signatures and docstrings.
autodoc_mock_imports = ["inspect_ai", "control_arena", "dotenv", "azure"]
autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "undoc-members": True, "show-inheritance": True}
autodoc_preserve_defaults = True

html_theme = "furo"
html_title = "probe & audit"
myst_enable_extensions = ["colon_fence", "deflist"]
exclude_patterns = ["_build"]
