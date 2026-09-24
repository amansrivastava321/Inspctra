"""
test_config_loader.py - Tests for safe CLI config loading.
"""

from pathlib import Path

from qa_ai.cli.config_loader import ConfigLoader


class TestConfigLoader:
    def test_load_yaml_success(self, tmp_dir):
        cfg = tmp_dir / "config.yaml"
        cfg.write_text("profiles:\n  web: web_app.yaml\n", encoding="utf-8")

        loaded = ConfigLoader(default_config_path=cfg).load_yaml(cfg)
        assert loaded["profiles"]["web"] == "web_app.yaml"

    def test_load_yaml_malformed_returns_empty(self, tmp_dir):
        cfg = tmp_dir / "broken.yaml"
        cfg.write_text("profiles: [unclosed\n", encoding="utf-8")

        loaded = ConfigLoader(default_config_path=cfg).load_yaml(cfg)
        assert loaded == {}

    def test_load_uses_default_fallback(self, tmp_dir):
        default_cfg = tmp_dir / "default.yaml"
        default_cfg.write_text("profiles:\n  api: api_service.yaml\n", encoding="utf-8")
        loader = ConfigLoader(default_config_path=default_cfg)

        loaded = loader.load(path=tmp_dir / "missing.yaml")
        assert loaded["profiles"]["api"] == "api_service.yaml"
