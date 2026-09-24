import qa_ai.cli.main as cli_main
from qa_ai.cli.main import main


class TestModelsCli:
    def test_models_doctor(self, tmp_dir, monkeypatch):
        def fake_models_doctor(self, output_dir="artifacts"):
            return {"status": "ok", "artifact": "model_routing_report.json"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_models_doctor", fake_models_doctor)
        rc = main(["models", "doctor", "--output-dir", str(tmp_dir / "artifacts")])
        assert rc == 0

    def test_models_routing(self, tmp_dir, monkeypatch):
        def fake_models_routing(self, artifacts_dir="artifacts"):
            return {"status": "ok", "artifact": "model_routing_report.json"}

        monkeypatch.setattr(cli_main.AuditCommand, "run_models_routing", fake_models_routing)
        rc = main(["models", "routing", str(tmp_dir / "artifacts")])
        assert rc == 0

    def test_models_test_component(self, tmp_dir, monkeypatch):
        captured = {}

        def fake_models_test(self, component, artifacts_dir="artifacts"):
            captured["component"] = component
            return {"status": "ok", "component": component}

        monkeypatch.setattr(cli_main.AuditCommand, "run_models_test", fake_models_test)
        rc = main([
            "models",
            "test",
            "--component",
            "master_orchestration",
            "--output-dir",
            str(tmp_dir / "artifacts"),
        ])
        assert rc == 0
        assert captured["component"] == "master_orchestration"

    def test_models_privacy_check(self, tmp_dir, monkeypatch):
        def fake_privacy(self, artifacts_dir="artifacts"):
            return {"status": "ok", "safe": True}

        monkeypatch.setattr(cli_main.AuditCommand, "run_models_privacy_check", fake_privacy)
        rc = main(["models", "privacy-check", "--output-dir", str(tmp_dir / "artifacts")])
        assert rc == 0
