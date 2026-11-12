"""
Guards against template mistakes that render as visible garbage.

Django's {# #} comment is single-line only: a multi-line one is not parsed as a
comment and its text is emitted into the page. Inside a <tbody> the HTML parser
then hoists that text out of the table, which also breaks the layout.
"""
import glob
import re

import pytest

TEMPLATES = sorted(
    glob.glob("order/templates/**/*.html", recursive=True)
    + glob.glob("templates/**/*.html", recursive=True)
)


@pytest.mark.parametrize("path", TEMPLATES)
def test_no_multiline_hash_comments(path):
    with open(path, encoding="utf-8") as handle:
        source = handle.read()

    offenders = [
        match.group(0)[:60]
        for match in re.finditer(r"\{#(.*?)#\}", source, re.DOTALL)
        if "\n" in match.group(1)
    ]

    assert not offenders, (
        f"{path} has a multi-line {{# #}} comment, which Django renders "
        f"literally. Use {{% comment %}}...{{% endcomment %}}: {offenders}"
    )
