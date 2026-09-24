"""
Verify that WorkflowEngine public API is fully preserved after mixin refactor.
These tests check method existence and inheritance, not behavior.
"""
import inspect
import pytest
from qa_ai.orchestration.workflow_engine import WorkflowEngine


def _get_all_run_methods():
    """Return all _run_* method names on WorkflowEngine."""
    return [name for name in dir(WorkflowEngine) if name.startswith("_run_")]


class TestPublicAPIPreserved:
    def test_run_method_exists(self):
        assert hasattr(WorkflowEngine, "run")
        assert callable(WorkflowEngine.run)

    def test_init_method_exists(self):
        assert hasattr(WorkflowEngine, "__init__")

    def test_all_run_methods_accessible(self):
        """All _run_* methods must be callable on WorkflowEngine."""
        wf_methods = _get_all_run_methods()
        assert len(wf_methods) > 50, f"Expected >50 _run_ methods, got {len(wf_methods)}"
        for method_name in wf_methods:
            method = getattr(WorkflowEngine, method_name)
            assert callable(method), f"{method_name} should be callable"

    def test_workflow_engine_importable(self):
        from qa_ai.orchestration.workflow_engine import WorkflowEngine, WorkflowPhase, PhaseResult
        assert WorkflowEngine is not None
        assert WorkflowPhase is not None
        assert PhaseResult is not None


class TestMixinInheritance:
    def test_workflow_engine_inherits_from_mixins(self):
        """After refactor, WorkflowEngine should inherit from at least one mixin."""
        bases = [b.__name__ for b in WorkflowEngine.__mro__]
        # At least one of these should be in the MRO after refactor
        mixin_names = {
            "AuditPhaseMixin", "LivePhaseMixin", "ImprovementPhaseMixin",
            "CICDPhaseMixin", "ExtendedPhaseMixin", "AIPhaseMixin"
        }
        found = mixin_names.intersection(set(bases))
        # This will fail before refactor (expected) and pass after
        assert len(found) > 0, (
            f"WorkflowEngine should inherit from at least one phase mixin. "
            f"MRO: {bases}"
        )
