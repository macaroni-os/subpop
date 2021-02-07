# Configuration file for the Sphinx documentation builder.

import os
import sys

sys.path.insert(0, os.path.abspath("../../subpop"))


# -- Project information -----------------------------------------------------

project = "subpop"
copyright = "2021, Daniel Robbins"
author = "Daniel Robbins"
html_context = {"project_url": "https://projects.funtoo.org/subpop"}
# The full version, including alpha/beta/rc tags
release = "0.1"

# -- General configuration ---------------------------------------------------


# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

master_doc = "index"


import sphinx_funtoo_theme

extensions = [
	"sphinx_funtoo_theme",
	"sphinx.ext.autosectionlabel",
	"sphinx.ext.autodoc",
]

html_theme = "sphinx_funtoo_theme"
