#!/usr/bin/env python3
"""
Test AIOps Agent with Demo Service

Run this from the aiops-agent-final directory.
"""

import sys
import os

# We're already in the right directory for imports
from src.agents.ops_commander import OpsCommander


def print_result(result, test_name):
    """Pretty print investigation results"""
    print(f"\n{'=' * 70}")
    print(f"🔍 {test_name}")
    print('=' * 70)

    if result.get("success"):
        print(f"\n✅ Investigation Successful")
        print(f"\n📊 Results:")
        print(f"   Service: {result.get('service_name')}")
        print(f"   Root Cause: {result.get('root_cause')}")
        print(f"   Confidence: {result.get('confidence', 0):.0%}")
        print(f"   Duration: {result.get('duration_seconds', 0):.2f}s")
        print(f"   Metrics Analyzed: {result.get('metrics_analyzed')}")
        print(f"   Logs Analyzed: {result.get('logs_analyzed')}")

        if result.get('time_window'):
            tw = result['time_window']
            print(f"\n⏰ Time Window:")
            print(f"   From: {tw.get('start')}")
            print(f"   To:   {tw.get('end')}")

        print(f"\n📝 Full Summary:")
        print("-" * 70)
        print(result.get('summary', 'No summary available'))

        if result.get('errors'):
            print(f"\n⚠️  Errors encountered: {len(result['errors'])}")
            for error in result['errors'][:3]:
                print(f"   • {error}")
    else:
        print(f"\n❌ Investigation Failed")
        print(f"   Error: {result.get('error')}")


def main():
    """Run AIOps Agent tests"""

    # Get project ID from environment or gcloud
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        import subprocess
        try:
            project_id = subprocess.check_output(
                ["gcloud", "config", "get-value", "project"],
                text=True
            ).strip()
        except:
            print("❌ Could not get GCP project ID")
            print("Set it with: export GCP_PROJECT_ID=your-project-id")
            sys.exit(1)

    service_name = sys.argv[1] if len(sys.argv) > 1 else "aiops-demo-service"

    print("\n" + "=" * 70)
    print(" " * 15 + "🤖 AIOps Agent - End-to-End Test")
    print("=" * 70)
    print(f"\nProject ID: {project_id}")
    print(f"Service Name: {service_name}")
    print("\n" + "=" * 70)

    # Initialize AIOps Agent
    print("\n🔧 Initializing AIOps Agent...")
    commander = OpsCommander(project_id=project_id, use_llm=False)
    print("✅ Agent initialized!\n")

    # Test Case 1: General health check
    print("\n" + "=" * 70)
    print("TEST 1: General Health Investigation")
    print("=" * 70)

    result1 = commander.handle_query(
        f"Check the health of {service_name}",
        service_name=service_name
    )
    print_result(result1, "General Health Check")

    # Test Case 2: Error investigation
    print("\n" + "=" * 70)
    print("TEST 2: Error Investigation")
    print("=" * 70)

    result2 = commander.handle_query(
        f"{service_name} is throwing errors",
        service_name=service_name
    )
    print_result(result2, "Error Investigation")

    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Summary")
    print("=" * 70)

    tests = [result1, result2]
    successful = sum(1 for r in tests if r.get('success'))

    print(f"\nTests Run: {len(tests)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(tests) - successful}")

    # Check if we got real data
    total_logs = sum(r.get('logs_analyzed', 0) for r in tests)
    total_metrics = sum(r.get('metrics_analyzed', 0) for r in tests)

    print(f"\n🔍 Data Analyzed:")
    print(f"  Total Logs: {total_logs}")
    print(f"  Total Metrics: {total_metrics}")

    if total_logs > 0:
        print(f"\n✅ SUCCESS! Your AIOps Agent found and analyzed real logs!")
        print(f"   This proves the system is working end-to-end! 🎉")
    else:
        print(f"\n⚠️  No logs found. Possible reasons:")
        print(f"   1. Service hasn't received traffic yet")
        print(f"   2. Logs haven't propagated (wait 2-3 minutes)")
        print(f"   3. Service name mismatch")
        print(f"\nCheck logs exist:")
        print(f'  gcloud logging read "resource.labels.service_name={service_name}" --limit=10')

    print("\n" + "=" * 70)
    print("✅ Testing Complete!")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()