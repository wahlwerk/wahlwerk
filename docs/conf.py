"""Sphinx configuration: the API reference of wahlwerk.

Build from the repository root:

    uv sync --group docs
    uv run sphinx-build -b html docs docs/_build/html

Every class, function, field and parameter is documented from the code: docstrings by
autodoc, every pydantic field with its ``Field(description=...)`` by autodoc_pydantic,
so the reference cannot drift from what the engine does. Concepts and examples live on
wahlwerk-site; this is the reference.
"""

from __future__ import annotations

import sys
from importlib.metadata import version as _version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "wahlwerk"
author = "Julius Sommer"
copyright = "2026, Julius Sommer"
release = _version("wahlwerk")

extensions = [
    "myst_parser",  # pages in Markdown
    "sphinx.ext.autodoc",  # docstrings
    "sphinx.ext.viewcode",  # [source] links next to every object
    "sphinx.ext.intersphinx",  # links into the Python and pydantic docs
    "sphinxcontrib.autodoc_pydantic",  # fields, defaults, descriptions, validators
    "sphinxcontrib.bibtex",  # references from the Zotero export
]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
myst_enable_extensions = ["colon_fence", "deflist"]
exclude_patterns = ["_build", "_statutes.md"]

# --- autodoc -------------------------------------------------------------------------
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "show-inheritance": True,
    "undoc-members": False,
}
autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_class_signature = "separated"
autodoc_preserve_defaults = True
add_module_names = False

# --- autodoc_pydantic: models read as what they are, frozen records of fields ---------
autodoc_pydantic_model_show_json = False
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_model_show_validator_summary = True
autodoc_pydantic_model_show_validator_members = True
autodoc_pydantic_model_show_field_summary = True
autodoc_pydantic_model_member_order = "bysource"
autodoc_pydantic_field_list_validators = True
autodoc_pydantic_field_show_constraints = True
autodoc_pydantic_field_show_default = True
autodoc_pydantic_field_doc_policy = "description"

# --- references: one BibTeX file, exported from Zotero (Better BibLaTeX) ---------------
bibtex_bibfiles = ["references.bib"]
bibtex_default_style = "unsrt"
bibtex_reference_style = "label"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest", None),
}

# --- statutes: generated from the law registry and statutes.toml, never written by hand -
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


def _write_statutes() -> None:
    """``docs/_statutes.md``: every statute version the engine implements (its Law
    objects) and every statute it only cites (``statutes.toml``). The site reads the
    same two sources, so both documentations cite the same versions."""
    from wahlwerk.law.registry import LAWS

    here = Path(__file__).parent
    cited = tomllib.loads((here / "statutes.toml").read_text(encoding="utf-8"))
    lines = [
        "| Law id | Statute | Version | In force |",
        "| --- | --- | --- | --- |",
    ]
    for law in sorted(LAWS.laws, key=lambda law: law.id):
        span = " to ".join(
            str(d) for d in (law.in_force_from, law.in_force_until) if d is not None
        )
        title = f"[{law.title}]({law.source})" if law.source else law.title
        lines.append(f"| `{law.id}` | {title} | {law.citation} | {span or 'not on record'} |")
    for law_id, entry in sorted(cited.items()):
        title = f"[{entry['title']}]({entry['source']}) ({entry['short']})"
        lines.append(f"| `{law_id}` | {title} | {entry['version']} | cited, not implemented |")
    (here / "_statutes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


_write_statutes()

html_theme = "furo"
html_title = f"wahlwerk {release}"
html_theme_options = {
    "source_repository": "https://github.com/wahlwerk/wahlwerk",
    "source_branch": "main",
    "source_directory": "docs/",
}
