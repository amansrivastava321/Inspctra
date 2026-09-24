"""
validation_profiles.py - Generic built-in target profile templates.

These are template factories only. No app-specific logic.
Callers set target_id, app_name, config_path, etc.
"""
from __future__ import annotations

from qa_ai.interactive_runtime.validation.validation_target import ValidationTarget


def web_target(
    target_id: str,
    app_name: str,
    config_path: str,
    validation_mode: str = "live_guided",
    max_actions: int = 15,
) -> ValidationTarget:
    return ValidationTarget(
        target_id=target_id,
        app_name=app_name,
        app_type="web",
        config_path=config_path,
        validation_mode=validation_mode,
        max_actions=max_actions,
        allow_real_launch="ask",
        allow_external_calls="ask",
        allow_database_checks=False,
        allow_screenshots="ask",
    )


def macos_target(
    target_id: str,
    app_name: str,
    config_path: str,
    validation_mode: str = "live_guided",
    max_actions: int = 20,
) -> ValidationTarget:
    return ValidationTarget(
        target_id=target_id,
        app_name=app_name,
        app_type="native_macos",
        config_path=config_path,
        expected_platform="darwin",
        validation_mode=validation_mode,
        max_actions=max_actions,
        allow_real_launch="ask",
        allow_external_calls="ask",
        allow_database_checks=False,
        allow_screenshots="ask",
        expected_capabilities=["can_observe_screen", "can_click"],
    )


def flutter_macos_target(
    target_id: str,
    app_name: str,
    config_path: str,
    validation_mode: str = "live_guided_ai",
    max_actions: int = 25,
) -> ValidationTarget:
    return ValidationTarget(
        target_id=target_id,
        app_name=app_name,
        app_type="flutter_macos",
        config_path=config_path,
        expected_platform="darwin",
        validation_mode=validation_mode,
        max_actions=max_actions,
        allow_real_launch="ask",
        allow_external_calls="ask",
        allow_database_checks=False,
        allow_screenshots="ask",
        notes="Flutter accessibility tree may be weak — testability_issues expected.",
    )


def flutter_web_target(
    target_id: str,
    app_name: str,
    config_path: str,
    validation_mode: str = "live_guided_ai",
    max_actions: int = 25,
) -> ValidationTarget:
    return ValidationTarget(
        target_id=target_id,
        app_name=app_name,
        app_type="flutter_web",
        config_path=config_path,
        validation_mode=validation_mode,
        max_actions=max_actions,
        allow_real_launch="ask",
        allow_external_calls="ask",
        allow_database_checks=False,
        allow_screenshots="ask",
    )


def android_target(
    target_id: str,
    app_name: str,
    config_path: str,
    max_actions: int = 20,
) -> ValidationTarget:
    return ValidationTarget(
        target_id=target_id,
        app_name=app_name,
        app_type="android",
        config_path=config_path,
        validation_mode="live_guided",
        max_actions=max_actions,
        allow_real_launch="ask",
        allow_external_calls="ask",
        allow_database_checks=False,
        allow_screenshots="ask",
        notes="Requires Appium server + device. Set mobile.appium_enabled=true in config.",
    )


def ios_target(
    target_id: str,
    app_name: str,
    config_path: str,
    max_actions: int = 20,
) -> ValidationTarget:
    return ValidationTarget(
        target_id=target_id,
        app_name=app_name,
        app_type="ios",
        config_path=config_path,
        expected_platform="darwin",
        validation_mode="live_guided",
        max_actions=max_actions,
        allow_real_launch="ask",
        allow_external_calls="ask",
        allow_database_checks=False,
        allow_screenshots="ask",
        notes="Requires macOS + Xcode + Appium XCUITest driver. Set mobile.appium_enabled=true.",
    )
