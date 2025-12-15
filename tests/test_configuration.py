"""Tests for Pydantic Settings configuration system."""


import pytest

from repo_minder import Settings


class TestSettingsDefaults:
    """Test default configuration values."""

    def test_default_organization(self):
        """Default organization should be 'mitre'."""
        settings = Settings()
        assert settings.organization == "mitre"

    def test_default_team(self):
        """Default team should be 'saf'."""
        settings = Settings()
        assert settings.team == "saf"

    def test_default_delay(self):
        """Default delay should be 0.5 seconds."""
        settings = Settings()
        assert settings.delay == 0.5

    def test_default_max_workers(self):
        """Default max workers should be 20."""
        settings = Settings()
        assert settings.max_workers == 20

    def test_default_skip_archived(self):
        """Default skip_archived should be False."""
        settings = Settings()
        assert settings.skip_archived is False

    def test_default_skip_forks(self):
        """Default skip_forks should be True."""
        settings = Settings()
        assert settings.skip_forks is True

    def test_default_log_level(self):
        """Default log level should be INFO."""
        settings = Settings()
        assert settings.log_level == "INFO"

    def test_default_backup_dir(self):
        """Default backup directory should be 'backups'."""
        settings = Settings()
        assert settings.backup_dir == "backups"

    def test_default_templates_dir(self):
        """Default templates directory should be 'templates'."""
        settings = Settings()
        assert settings.templates_dir == "templates"

    def test_default_case_number(self):
        """Default case number should be '18-3678'."""
        settings = Settings()
        assert settings.case_number == "18-3678"

    def test_default_copyright_org(self):
        """Default copyright org should be 'The MITRE Corporation'."""
        settings = Settings()
        assert settings.copyright_org == "The MITRE Corporation"


class TestEnvironmentVariableOverrides:
    """Test environment variable configuration."""

    def test_org_from_env(self, monkeypatch):
        """REPO_MINDER_ORGANIZATION should override default."""
        monkeypatch.setenv("REPO_MINDER_ORGANIZATION", "test-org")
        settings = Settings()
        assert settings.organization == "test-org"

    def test_team_from_env(self, monkeypatch):
        """REPO_MINDER_TEAM should override default."""
        monkeypatch.setenv("REPO_MINDER_TEAM", "test-team")
        settings = Settings()
        assert settings.team == "test-team"

    def test_delay_from_env(self, monkeypatch):
        """REPO_MINDER_DELAY should override default."""
        monkeypatch.setenv("REPO_MINDER_DELAY", "1.5")
        settings = Settings()
        assert settings.delay == 1.5

    def test_max_workers_from_env(self, monkeypatch):
        """REPO_MINDER_MAX_WORKERS should override default."""
        monkeypatch.setenv("REPO_MINDER_MAX_WORKERS", "30")
        settings = Settings()
        assert settings.max_workers == 30

    def test_skip_archived_from_env(self, monkeypatch):
        """REPO_MINDER_SKIP_ARCHIVED should override default."""
        monkeypatch.setenv("REPO_MINDER_SKIP_ARCHIVED", "true")
        settings = Settings()
        assert settings.skip_archived is True

    def test_skip_forks_from_env(self, monkeypatch):
        """REPO_MINDER_SKIP_FORKS should override default."""
        monkeypatch.setenv("REPO_MINDER_SKIP_FORKS", "false")
        settings = Settings()
        assert settings.skip_forks is False

    def test_log_level_from_env(self, monkeypatch):
        """REPO_MINDER_LOG_LEVEL should override default."""
        monkeypatch.setenv("REPO_MINDER_LOG_LEVEL", "DEBUG")
        settings = Settings()
        assert settings.log_level == "DEBUG"

    def test_backup_dir_from_env(self, monkeypatch):
        """REPO_MINDER_BACKUP_DIR should override default."""
        monkeypatch.setenv("REPO_MINDER_BACKUP_DIR", "/tmp/backups")
        settings = Settings()
        assert settings.backup_dir == "/tmp/backups"

    def test_case_number_from_env(self, monkeypatch):
        """REPO_MINDER_CASE_NUMBER should override default."""
        monkeypatch.setenv("REPO_MINDER_CASE_NUMBER", "99-9999")
        settings = Settings()
        assert settings.case_number == "99-9999"

    def test_copyright_org_from_env(self, monkeypatch):
        """REPO_MINDER_COPYRIGHT_ORG should override default."""
        monkeypatch.setenv("REPO_MINDER_COPYRIGHT_ORG", "Test Corporation")
        settings = Settings()
        assert settings.copyright_org == "Test Corporation"


class TestSettingsValidation:
    """Test Pydantic validation rules."""

    def test_delay_must_be_positive(self, monkeypatch):
        """Delay must be >= 0.0."""
        monkeypatch.setenv("REPO_MINDER_DELAY", "-1.0")
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            Settings()

    def test_delay_has_maximum(self, monkeypatch):
        """Delay must be <= 5.0."""
        monkeypatch.setenv("REPO_MINDER_DELAY", "10.0")
        with pytest.raises(ValueError, match="less than or equal to 5"):
            Settings()

    def test_max_workers_minimum(self, monkeypatch):
        """Max workers must be >= 1."""
        monkeypatch.setenv("REPO_MINDER_MAX_WORKERS", "0")
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            Settings()

    def test_max_workers_maximum(self, monkeypatch):
        """Max workers must be <= 50."""
        monkeypatch.setenv("REPO_MINDER_MAX_WORKERS", "100")
        with pytest.raises(ValueError, match="less than or equal to 50"):
            Settings()


class TestDotEnvFileLoading:
    """Test .env file loading."""

    def test_loads_from_env_file(self, tmp_path, monkeypatch):
        """Settings should load from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("REPO_MINDER_ORGANIZATION=dotenv-org\n")

        # Change to tmp directory so it finds the .env file
        monkeypatch.chdir(tmp_path)

        # Override env_file location for this test
        settings = Settings(_env_file=str(env_file))
        assert settings.organization == "dotenv-org"

    def test_env_vars_override_env_file(self, tmp_path, monkeypatch):
        """Environment variables should override .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("REPO_MINDER_ORGANIZATION=dotenv-org\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("REPO_MINDER_ORGANIZATION", "env-var-org")

        settings = Settings(_env_file=str(env_file))
        # Env var should win
        assert settings.organization == "env-var-org"

    def test_works_without_env_file(self):
        """Settings should work even if .env doesn't exist."""
        settings = Settings(_env_file="nonexistent.env")
        assert settings.organization == "mitre"  # Uses defaults


class TestRepoMinderWithSettings:
    """Test RepoMinder class uses settings correctly."""

    def test_uses_settings_for_defaults(self):
        """RepoMinder should use global settings for defaults."""
        from repo_minder import RepoMinder, settings

        minder = RepoMinder()
        assert minder.organization == settings.organization
        assert minder.team == settings.team
        assert minder.delay == settings.delay
        assert minder.max_workers == settings.max_workers

    def test_constructor_params_override_settings(self, monkeypatch):
        """Constructor params should override settings."""
        from repo_minder import RepoMinder

        monkeypatch.setenv("REPO_MINDER_ORGANIZATION", "env-org")

        minder = RepoMinder(organization="param-org")
        assert minder.organization == "param-org"  # Param wins

    def test_none_param_uses_settings(self):
        """Passing None should fall back to settings."""
        from repo_minder import RepoMinder, settings

        minder = RepoMinder(organization=None)
        assert minder.organization == settings.organization
