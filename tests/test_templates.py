"""Unit tests for LICENSE template content and structure."""



class TestTemplateStructure:
    """Test that templates have correct structure and content."""

    def test_cis_template_has_cis_section(self, cis_template):
        """CIS template must contain CIS Benchmarks third-party section."""
        assert "CIS Benchmarks" in cis_template
        assert "www.cisecurity.org" in cis_template
        assert "## Third-Party Content" in cis_template

    def test_disa_template_has_disa_section(self, disa_template):
        """DISA template must contain DISA STIGs third-party section."""
        assert "DISA STIGs" in disa_template or "DISA IASE" in disa_template
        assert "public.cyber.mil/stigs" in disa_template or "iase.disa.mil" in disa_template
        assert "## Third-Party Content" in disa_template

    def test_plain_template_no_third_party(self, plain_template):
        """Plain template should not have third-party section."""
        assert "## Third-Party Content" not in plain_template
        assert "CIS Benchmarks" not in plain_template
        assert "DISA STIGs" not in plain_template

    def test_all_templates_have_apache_license(self, cis_template, disa_template, plain_template):
        """All templates must contain Apache 2.0 license."""
        for template in [cis_template, disa_template, plain_template]:
            assert "Apache License, Version 2.0" in template
            assert "http://www.apache.org/licenses/LICENSE-2.0" in template

    def test_all_templates_have_mitre_copyright(self, cis_template, disa_template, plain_template):
        """All templates must contain MITRE copyright."""
        for template in [cis_template, disa_template, plain_template]:
            assert (
                "© 2025 The MITRE Corporation" in template
                or "Copyright © 2025 The MITRE Corporation" in template
            )

    def test_all_templates_have_government_notice(
        self, cis_template, disa_template, plain_template
    ):
        """All templates must contain government contract notice."""
        for template in [cis_template, disa_template, plain_template]:
            assert "U.S. Government" in template
            assert "Case Number 18-3678" in template

    def test_all_templates_80_char_width(self, cis_template, disa_template, plain_template):
        """All templates should respect 80-character line width."""
        for name, template in [
            ("CIS", cis_template),
            ("DISA", disa_template),
            ("Plain", plain_template),
        ]:
            lines = template.split("\n")
            long_lines = [
                i + 1
                for i, line in enumerate(lines)
                if len(line) > 80 and not line.strip().startswith("http")
            ]
            assert len(long_lines) == 0, f"{name} template has lines > 80 chars at: {long_lines}"

    def test_cis_template_structure(self, cis_template):
        """CIS template must have all required sections."""
        required_sections = [
            "# License",
            "## Redistribution Terms",
            "## Third-Party Content",
            "## Notice",
        ]
        for section in required_sections:
            assert section in cis_template, f"CIS template missing section: {section}"

    def test_disa_template_structure(self, disa_template):
        """DISA template must have all required sections."""
        required_sections = [
            "# License",
            "## Redistribution Terms",
            "## Notice",
            "## Third-Party Content",
        ]
        for section in required_sections:
            assert section in disa_template, f"DISA template missing section: {section}"

    def test_plain_template_structure(self, plain_template):
        """Plain template must have required sections (no third-party)."""
        required_sections = [
            "# License",
            "## Redistribution Terms",
            "## Notice",
        ]
        for section in required_sections:
            assert section in plain_template, f"Plain template missing section: {section}"
