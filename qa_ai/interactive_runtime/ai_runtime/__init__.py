"""
ai_runtime - Hybrid AI-Native Interactive Runtime Tester.

Layered on top of the deterministic interactive_runtime layer.

Core principle: AI figures things out. Evidence proves whether it was right.
PASS requires evidence. AI opinion alone → UNCLEAR.
"""
from __future__ import annotations

from qa_ai.interactive_runtime.ai_runtime.vision_screen_analyzer import VisionScreenAnalyzer
from qa_ai.interactive_runtime.ai_runtime.ai_action_decider import AIActionDecider
from qa_ai.interactive_runtime.ai_runtime.intent_inference import IntentInferenceEngine
from qa_ai.interactive_runtime.ai_runtime.ai_oracle import AIOracle
from qa_ai.interactive_runtime.ai_runtime.evidence_grounder import EvidenceGrounder
from qa_ai.interactive_runtime.ai_runtime.curiosity_engine import CuriosityEngine
from qa_ai.interactive_runtime.ai_runtime.step_narrator import StepNarrator
from qa_ai.interactive_runtime.ai_runtime.guided_trace_writer import GuidedTraceWriter
from qa_ai.interactive_runtime.ai_runtime.confidence_calibrator import ConfidenceCalibrator
from qa_ai.interactive_runtime.ai_runtime.safety_filter import SafetyFilter

__all__ = [
    "VisionScreenAnalyzer",
    "AIActionDecider",
    "IntentInferenceEngine",
    "AIOracle",
    "EvidenceGrounder",
    "CuriosityEngine",
    "StepNarrator",
    "GuidedTraceWriter",
    "ConfidenceCalibrator",
    "SafetyFilter",
]
