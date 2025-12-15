"""Test that Jinja2 templates produce equivalent output to static templates."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from standardize_licenses import HAS_JINJA2, TEMPLATE_VARS

pytestmark = pytest.mark.skipif(not HAS_JINJA2, reason="Jinja2 not installed")


class TestJinja2EquivalenceToStatic:
    """Verify Jinja2 output has same content as static templates (not necessarily exact match)."""

    def test_jinja2_cis_has_same_content_as_static(self, jinja_env, cis_template):
        """Jinja2 CIS should have same sections as static CIS."""
        template = jinja_env.get_template("cis.j2")
        jinja_output = template.render(**TEMPLATE_VARS)

        # Check all required sections exist in both
        required_content = [
            "# License",
            "Apache License, Version 2.0",
            "## Redistribution Terms",
            "## Third-Party Content",
            "CIS Benchmarks",
            "www.cisecurity.org",
            "## Notice",
            "U.S. Government",
            "Case Number 18-3678",
        ]

        for content in required_content:
            assert content in jinja_output, f"Jinja2 missing: {content}"
            assert content in cis_template, f"Static missing: {content}"

    def test_jinja2_disa_has_same_content_as_static(self, jinja_env, disa_template):
        """Jinja2 DISA should have same sections as static DISA."""
        template = jinja_env.get_template("disa.j2")
        jinja_output = template.render(**TEMPLATE_VARS)

        # Check all required sections exist in both
        required_content = [
            "# License",
            "Apache License, Version 2.0",
            "## Redistribution Terms",
            "## Third-Party Content",
            "DISA STIGs",
            "## Notice",
            "U.S. Government",
        ]

        for content in required_content:
            assert content in jinja_output, f"Jinja2 missing: {content}"
            # DISA template might have different wording
            if content == "DISA STIGs":
                assert "DISA" in disa_template, "Static missing DISA reference"
            else:
                assert content in disa_template, f"Static missing: {content}"

    def test_jinja2_plain_has_same_content_as_static(self, jinja_env, plain_template):
        """Jinja2 plain should have same sections as static plain."""
        template = jinja_env.get_template("plain.j2")
        jinja_output = template.render(**TEMPLATE_VARS)

        # Check all required sections exist in both
        required_content = [
            "# License",
            "Apache License, Version 2.0",
            "## Redistribution Terms",
            "## Notice",
            "U.S. Government",
        ]

        for content in required_content:
            assert content in jinja_output, f"Jinja2 missing: {content}"
            assert content in plain_template, f"Static missing: {content}"

        # Plain should NOT have third-party content
        assert "## Third-Party Content" not in jinja_output
        assert "## Third-Party Content" not in plain_template
