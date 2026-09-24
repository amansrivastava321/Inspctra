"""
qa_ai.interactive_runtime.setup
Runtime Environment Doctor + Auto-Setup for Inspectra.
"""
from qa_ai.interactive_runtime.setup.setup_models import (
    ActionRisk,
    ActionStatus,
    ActionType,
    EnvironmentDoctorReport,
    SetupAction,
    SetupActionResult,
    SetupExecutionLog,
    SetupPlan,
)
from qa_ai.interactive_runtime.setup.environment_doctor import EnvironmentDoctor
from qa_ai.interactive_runtime.setup.setup_plan import SetupPlanner
from qa_ai.interactive_runtime.setup.setup_runner import SetupRunner
from qa_ai.interactive_runtime.setup.dependency_installer import DependencyInstaller
from qa_ai.interactive_runtime.setup.permission_assistant import PermissionAssistant
from qa_ai.interactive_runtime.setup.platform_setup import (
    get_platform_setup_notes,
    get_required_packages_for_platform,
)
from qa_ai.interactive_runtime.setup.setup_reporter import SetupReporter
from qa_ai.interactive_runtime.setup.driver_requirements import (
    DriverRequirement,
    get_driver_requirements,
    get_all_requirements,
    get_requirements_for_types,
    registry_to_dict,
)

__all__ = [
    "ActionRisk",
    "ActionStatus",
    "ActionType",
    "EnvironmentDoctorReport",
    "SetupAction",
    "SetupActionResult",
    "SetupExecutionLog",
    "SetupPlan",
    "EnvironmentDoctor",
    "SetupPlanner",
    "SetupRunner",
    "DependencyInstaller",
    "PermissionAssistant",
    "get_platform_setup_notes",
    "get_required_packages_for_platform",
    "SetupReporter",
    "DriverRequirement",
    "get_driver_requirements",
    "get_all_requirements",
    "get_requirements_for_types",
    "registry_to_dict",
]
