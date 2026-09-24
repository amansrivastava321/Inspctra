"""
ai/__init__.py - AI package initialization.
Exports core classes for clean imports across the platform.
"""

from qa_ai.ai.ollama_client import OllamaClient
from qa_ai.ai.llm_router import LLMRouter, get_router
from qa_ai.ai.model_router import ModelRouter
from qa_ai.ai.task_router import ModelCallResult, TaskRouter, get_task_router
from qa_ai.ai.task_profiles import ModelTask, TaskRoute, ResourceProfile, MAC_M4_16GB
from qa_ai.ai.test_plan_generator import AITestPlanGenerator
from qa_ai.ai.evidence_evaluator import AIEvidenceEvaluator

__all__ = [
    "OllamaClient",
    "LLMRouter",
    "ModelRouter",
    "get_router",
    "ModelCallResult",
    "TaskRouter",
    "get_task_router",
    "ModelTask",
    "TaskRoute",
    "ResourceProfile",
    "MAC_M4_16GB",
    "AITestPlanGenerator",
    "AIEvidenceEvaluator",
]
