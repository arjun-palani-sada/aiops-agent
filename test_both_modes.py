
# !/usr/bin/env python3
"""Test AIOps Agent in both modes"""

# Load .env at the very top!
from src.config import Config
Config.load()

import os
import sys


project_id = os.popen("gcloud config get-value project").read().strip()
service_name = sys.argv[1] if len(sys.argv) > 1 else "aiops-demo-service"

# Check for API key
has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))

if has_api_key:
    print("✅ GOOGLE_API_KEY found - will test AI mode")
    mode = input("\nChoose mode (rules/ai/both) [both]: ").strip().lower() or "both"
else:
    print("⚠️  No GOOGLE_API_KEY - using rule-based mode only")
    mode = "rules"

from src.agents.ops_commander import OpsCommander

if mode in ["rules", "both"]:
    print("\n" + "=" * 70)
    print("📊 Testing: Rule-Based Mode")
    print("=" * 70)

    commander = OpsCommander(project_id=project_id, use_llm=False)
    result = commander.handle_query(f"{service_name} has errors")

    print(f"\nRoot Cause: {result['root_cause']}")
    print(f"Confidence: {result['confidence']:.0%}")
    print(f"Duration: {result['duration_seconds']:.2f}s")

if mode in ["ai", "both"] and has_api_key:
    print("\n" + "=" * 70)
    print("🤖 Testing: AI-Powered Mode")
    print("=" * 70)

    commander = OpsCommander(project_id=project_id, use_llm=True)
    result = commander.handle_query(f"{service_name} has errors")

    print(f"\nRoot Cause: {result['root_cause']}")
    print(f"Confidence: {result['confidence']:.0%}")
    print(f"Duration: {result['duration_seconds']:.2f}s")
    print(f"\nFull Summary:\n{result['summary']}")

print("\n✅ Testing complete!")