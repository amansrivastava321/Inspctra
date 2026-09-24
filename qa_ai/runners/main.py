import argparse
from pathlib import Path

from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.agents.generate_app_map import generate_app_map
from qa_ai.agents.llm_test_planner import LLMTestPlanner


def main():
    parser = argparse.ArgumentParser(description="Autonomous QA Platform")
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--path", required=True)
    args = parser.parse_args()

    app_path = Path(args.path).expanduser().resolve()
    if not app_path.exists():
        raise FileNotFoundError(f"Path does not exist: {app_path}")

    store = ArtifactStore()

    print("\n=== Autonomous QA Platform ===")
    print(f"Auditing: {args.app_name}")
    print(f"Location: {app_path}")

    # Phase 1: Discovery
    print("\n[1] Discovery Agent running...")
    app_map = generate_app_map(app_path, artifact_store=store)

    # Get nested values safely
    stack = app_map.get("stack", {}) or {}
    caps = stack.get("capabilities", {}) or {}

    print("\n=== Stack Intelligence ===")
    print(f"Framework: {stack.get('framework', 'unknown')}")
    print(f"Language: {stack.get('language', 'unknown')}")
    print(f"App Type: {stack.get('app_type', 'unknown')}")
    print(f"Confidence: {stack.get('confidence', 'unknown')}")

    print("\n=== Capabilities ===")
    print(f"Auth: {caps.get('has_auth', False)}")
    print(f"Database: {caps.get('has_database', False)}")
    print(f"Payments: {caps.get('has_payments', False)}")
    print(f"Realtime: {caps.get('has_real_time', False)}")
    print(f"E2E Tests: {caps.get('has_e2e_tests', False)}")

    print("\n=== Discovery ===")
    print(f"Routes found: {len(app_map.get('routes', []))}")
    print(f"APIs found: {len(app_map.get('api_endpoints', []))}")

    # Phase 2: Test Planning
    print("\n[2] Test Planner Agent generating test plan...")
    try:
        planner = LLMTestPlanner(artifact_store=store)
        test_plan = planner.generate_plan(app_map)

        print(f"\n=== Test Plan Generated ===")
        print(f"Total tests: {test_plan['summary']['total_tests']}")
        for suite, count in test_plan['summary']['by_suite'].items():
            print(f"  {suite}: {count}")
        print(f"\nBy priority:")
        for priority, count in test_plan['summary']['by_priority'].items():
            print(f"  {priority}: {count}")
    except Exception as e:
        print(f"  Test planner failed (Ollama may not be running): {e}")

    print("\n=== Artifacts Generated ===")
    print("artifacts/app_map.json")
    print("artifacts/test_plan.json")
    print("\nDone.")


if __name__ == "__main__":
    main()