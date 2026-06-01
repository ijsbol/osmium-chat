"""Sphinx configuration for the osmium_chat documentation.

Built automatically by Read the Docs (see ``.readthedocs.yaml``), which installs
the package and its dependencies so autodoc can import it.
"""

import os
import sys
from datetime import datetime

# Make the package importable when building from a source checkout.
sys.path.insert(0, os.path.abspath(".."))

# -- Project information ------------------------------------------------------

project = "osmium_chat"
author = "abigail phoebe"
copyright = f"{datetime.now():%Y}, {author}"

try:
    from osmium_chat import __version__ as release
except Exception:
    release = "0.0.0"
version = release

# -- General configuration ----------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_member_order = "bysource"
autodoc_typehints = "description"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# -- HTML output --------------------------------------------------------------

html_theme = "furo"
html_title = f"{project} {release}"
