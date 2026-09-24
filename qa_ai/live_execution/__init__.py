"""
qa_ai/live_execution/__init__.py
Live Execution Infrastructure - real browser/API execution with
trace capture, network recording, session management, replay, and visual regression.
"""

from qa_ai.live_execution.playwright_engine import PlaywrightEngine
from qa_ai.live_execution.browser_trace_manager import BrowserTraceManager
from qa_ai.live_execution.network_capture import NetworkCapture
from qa_ai.live_execution.session_manager import SessionManager
from qa_ai.live_execution.api_session_manager import APISessionManager
from qa_ai.live_execution.live_scenario_runner import LiveScenarioRunner
from qa_ai.live_execution.trace_recorder import TraceRecorder
from qa_ai.live_execution.replay_engine import ReplayEngine
from qa_ai.live_execution.visual_regression import VisualRegression
from qa_ai.live_execution.har_analyzer import HARAnalyzer

__all__ = [
    "PlaywrightEngine",
    "BrowserTraceManager",
    "NetworkCapture",
    "SessionManager",
    "APISessionManager",
    "LiveScenarioRunner",
    "TraceRecorder",
    "ReplayEngine",
    "VisualRegression",
    "HARAnalyzer",
]
