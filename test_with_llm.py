import os
from src.agents.ops_commander import OpsCommander

# Make sure API key is set
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("❌ Please set GOOGLE_API_KEY")
    exit(1)

print("✅ API Key found")
print("\n" + "="*70)
print("Testing AIOps Agent with AI-Powered Analysis")
print("="*70)

# Get project
project_id = os.popen("gcloud config get-value project").read().strip()

# Initialize with LLM enabled
commander = OpsCommander(project_id=project_id, use_llm=True)

# Test
result = commander.handle_query(
    "aiops-demo-service has permission errors",
    service_name="aiops-demo-service"
)

print("\n" + "="*70)
print("🤖 AI-Powered Investigation Results")
print("="*70)
print(f"\nService: {result['service_name']}")
print(f"Root Cause: {result['root_cause']}")
print(f"Confidence: {result['confidence']:.0%}")
print(f"Duration: {result['duration_seconds']:.2f}s")
print(f"\n{result['summary']}")