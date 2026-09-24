"""
model_runtime/__init__.py - Adaptive model runtime profiles for Inspectra.

Exports core classes for hardware-aware model routing.
"""
from qa_ai.model_runtime.hardware_detector import detect_hardware, HardwareProfile
from qa_ai.model_runtime.adaptive_profiles import (
    AdaptiveResourceProfile,
    get_all_profiles,
    get_profile_by_id,
    LOW_RAM_8GB,
    MAC_M4_16GB_ADAPTIVE,
    PRO_32GB,
    WORKSTATION_64GB,
    REMOTE_GPU,
)
from qa_ai.model_runtime.model_catalog import ModelCatalog, ModelCapability, get_default_catalog
from qa_ai.model_runtime.provider_discovery import discover_providers, DiscoveredProvider
from qa_ai.model_runtime.profile_selector import select_profile, SelectedModelRuntimeProfile
from qa_ai.model_runtime.adaptive_router import AdaptiveRouter, RouteDecision
from qa_ai.model_runtime.profile_reporter import build_profile_report

__all__ = [
    "detect_hardware",
    "HardwareProfile",
    "AdaptiveResourceProfile",
    "get_all_profiles",
    "get_profile_by_id",
    "LOW_RAM_8GB",
    "MAC_M4_16GB_ADAPTIVE",
    "PRO_32GB",
    "WORKSTATION_64GB",
    "REMOTE_GPU",
    "ModelCatalog",
    "ModelCapability",
    "get_default_catalog",
    "discover_providers",
    "DiscoveredProvider",
    "select_profile",
    "SelectedModelRuntimeProfile",
    "AdaptiveRouter",
    "RouteDecision",
    "build_profile_report",
]
