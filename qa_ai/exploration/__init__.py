"""
qa_ai/exploration/__init__.py - UI Exploration package initialization.
"""

from qa_ai.exploration.state_tracker import StateTracker, PageState
from qa_ai.exploration.navigation_graph import NavigationGraph, NavigationEdge
from qa_ai.exploration.form_detector import FormDetector, DetectedForm, DetectedInput
from qa_ai.exploration.dom_analyzer import DOMAnalyzer, ClickableElement
from qa_ai.exploration.interaction_engine import InteractionEngine, SafeAction
from qa_ai.exploration.ui_explorer import UIExplorer

__all__ = [
    "StateTracker",
    "PageState",
    "NavigationGraph",
    "NavigationEdge",
    "FormDetector",
    "DetectedForm",
    "DetectedInput",
    "DOMAnalyzer",
    "ClickableElement",
    "InteractionEngine",
    "SafeAction",
    "UIExplorer",
]
