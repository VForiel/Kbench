# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path('..', 'src').resolve()))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'PHOBos'
author = 'Photonics'
year = datetime.now().year
copyright = f'{year}, {author}'
repository_url = 'https://github.com/Kernel-Nulling/Test-bench-controls'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]

# Use NumPy format by default (True)
napoleon_google_docstring = False
napoleon_numpy_docstring = True

# Additional options (often useful)
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_use_param = True
napoleon_use_rtype = True

autodoc_member_order = 'bysource'
autodoc_typehints = 'signature'
autodoc_default_options = {
    'members': True,
    'show-inheritance': True,
}

autodoc_mock_imports = [
    "bmc",
    "serial",
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.animation",
    "xaosim",
    "xaosim.shmlib",
    "astropy",
    "scipy",
    "toml",
    "pylablib",
    "pylablib.devices",
    "pylablib.devices.Thorlabs",
    "numba",
]

# Keep strict builds useful while ignoring unresolved external symbols used in docstrings.
nitpick_ignore = [
    ("py:class", "optional"),
    ("py:class", "ndarray"),
    ("py:class", "serial.Serial"),
]

myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', '.venv']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'breeze'
html_static_path = ['_static']

# Breeze theme configuration
html_title = "PHOBos"
html_context = {
    "github_user": "Kernel-Nulling",
    "github_repo": "Test-bench-controls",
    "github_version": "main",
    "doc_path": "docs",
}

html_theme_options = {
    "emojis_header_nav": True,
}
