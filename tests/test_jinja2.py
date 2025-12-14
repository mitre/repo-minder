"""Tests for Jinja2 template rendering."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from standardize_licenses import HAS_JINJA2, JINJA_TEMPLATE, TEMPLATE_VARS

# Skip tests if Jinja2 not available
pytestmark = pytest.mark.skipif(not HAS_JINJA2, reason="Jinja2 not installed")


class TestJinja2Templates:
    """Test Jinja2 template rendering."""


    def test_jinja_template_exists(self):
        """Test that LICENSE.j2 template exists."""
        assert JINJA_TEMPLATE.exists(), "LICENSE.j2 template should exist"

    def test_renders_cis_template(self, jinja_env):
        """Test rendering CIS template with Jinja2."""
        template = jinja_env.get_template("LICENSE.j2")
        rendered = template.render(template_type="cis", **TEMPLATE_VARS)

        assert "CIS Benchmarks" in rendered
        assert "www.cisecurity.org" in rendered
        assert "## Third-Party Content" in rendered
        assert f"© {TEMPLATE_VARS['year']}" in rendered or f"Copyright © {TEMPLATE_VARS['year']}" in rendered

    def test_renders_disa_template(self, jinja_env):
        """Test rendering DISA template with Jinja2."""
        template = jinja_env.get_template("LICENSE.j2")
        rendered = template.render(template_type="disa", **TEMPLATE_VARS)

        assert "DISA STIGs" in rendered
        assert "public.cyber.mil/stigs" in rendered
        assert "## Third-Party Content" in rendered
        assert f"Case Number {TEMPLATE_VARS['case_number']}" in rendered

    def test_renders_plain_template(self, jinja_env):
        """Test rendering plain template with Jinja2."""
        template = jinja_env.get_template("LICENSE.j2")
        rendered = template.render(template_type="plain", **TEMPLATE_VARS)

        assert "CIS Benchmarks" not in rendered
        assert "DISA STIGs" not in rendered
        assert "## Third-Party Content" not in rendered
        assert "Apache License, Version 2.0" in rendered

    def test_template_variables_substituted(self, jinja_env):
        """Test that template variables are properly substituted."""
        template = jinja_env.get_template("LICENSE.j2")
        rendered = template.render(template_type="plain", year=2025, case_number="TEST-123")

        assert "© 2025" in rendered or "Copyright © 2025" in rendered
        assert "Case Number TEST-123" in rendered

    def test_all_rendered_templates_80_char_width(self, jinja_env):
        """Test that all rendered templates respect 80-char width."""
        template = jinja_env.get_template("LICENSE.j2")

        for template_type in ["cis", "disa", "plain"]:
            rendered = template.render(template_type=template_type, **TEMPLATE_VARS)
            lines = rendered.split("\n")
            long_lines = [
                i+1 for i, line in enumerate(lines)
                if len(line) > 80 and not line.strip().startswith("http")
            ]
            assert len(long_lines) == 0, f"{template_type} template has lines > 80 chars at: {long_lines}"


class TestTemplateEquivalence:
    """Test that Jinja2 templates match static templates."""

    def test_jinja_cis_matches_static_cis(self, jinja_env, cis_template):
        """Test that Jinja2 CIS template matches static CIS template."""
        jinja_template = jinja_env.get_template("LICENSE.j2")
        rendered = jinja_template.render(template_type="cis", **TEMPLATE_VARS)

        # Both should have same key content
        assert "CIS Benchmarks" in rendered
        assert "CIS Benchmarks" in cis_template
        assert "www.cisecurity.org" in rendered
        assert "www.cisecurity.org" in cis_template

    def test_jinja_disa_matches_static_disa(self, jinja_env, disa_template):
        """Test that Jinja2 DISA template matches static DISA template."""
        jinja_template = jinja_env.get_template("LICENSE.j2")
        rendered = jinja_template.render(template_type="disa", **TEMPLATE_VARS)

        # Both should have same key content
        assert "DISA STIGs" in rendered or "DISA IASE" in rendered
        assert "DISA STIGs" in disa_template or "DISA IASE" in disa_template

    def test_jinja_plain_matches_static_plain(self, jinja_env, plain_template):
        """Test that Jinja2 plain template matches static plain template."""
        jinja_template = jinja_env.get_template("LICENSE.j2")
        rendered = jinja_template.render(template_type="plain", **TEMPLATE_VARS)

        # Both should NOT have third-party content
        assert "## Third-Party Content" not in rendered
        assert "## Third-Party Content" not in plain_template
