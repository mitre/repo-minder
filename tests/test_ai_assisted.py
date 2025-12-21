"""Unit tests for AI-assisted LICENSE template content and CLI options."""


class TestAIAssistedTemplates:
    """Test that AI-assisted templates have correct AI disclosure."""

    def test_plain_template_with_ai_has_ai_disclosure(self, plain_template_ai):
        """Plain template with AI flag must contain AI disclosure."""
        assert "generative AI" in plain_template_ai
        assert "direction and review" in plain_template_ai
        assert "development efficiency" in plain_template_ai
        assert "standard quality and assurance testing" in plain_template_ai

    def test_plain_template_without_ai_has_no_disclosure(self, plain_template):
        """Plain template without AI flag should not have AI disclosure."""
        assert "generative AI" not in plain_template

    def test_cis_template_with_ai_has_ai_disclosure(self, cis_template_ai):
        """CIS template with AI flag must contain AI disclosure."""
        assert "generative AI" in cis_template_ai
        assert "direction and review" in cis_template_ai

    def test_disa_template_with_ai_has_ai_disclosure(self, disa_template_ai):
        """DISA template with AI flag must contain AI disclosure."""
        assert "generative AI" in disa_template_ai
        assert "direction and review" in disa_template_ai

    def test_ai_templates_still_have_all_required_sections(
        self, plain_template_ai, cis_template_ai, disa_template_ai
    ):
        """AI-assisted templates must still have all required sections."""
        for template in [plain_template_ai, cis_template_ai, disa_template_ai]:
            assert "# License" in template
            assert "## Redistribution Terms" in template
            assert "## Notice" in template
            assert "Apache License, Version 2.0" in template

    def test_ai_templates_have_correct_line_width(
        self, plain_template_ai, cis_template_ai, disa_template_ai
    ):
        """AI-assisted templates should respect 80-character line width."""
        for name, template in [
            ("Plain AI", plain_template_ai),
            ("CIS AI", cis_template_ai),
            ("DISA AI", disa_template_ai),
        ]:
            lines = template.split("\n")
            long_lines = [
                i + 1
                for i, line in enumerate(lines)
                if len(line) > 80 and not line.strip().startswith("http")
            ]
            assert len(long_lines) == 0, f"{name} template has lines > 80 chars at: {long_lines}"
