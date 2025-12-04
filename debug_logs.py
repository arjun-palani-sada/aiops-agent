
import os
from src.core import StateManager
from src.agents import MetricScout, LogCollector
from src.mcp import GCPMonitoringServer, GCPLoggingServer

project_id = os.popen("gcloud config get-value project").read().strip()

# Initialize
monitoring = GCPMonitoringServer(project_id)
logging_server = GCPLoggingServer(project_id)
scout = MetricScout(monitoring)
collector = LogCollector(logging_server)

# Create state
state = StateManager.create_initial_state(
    intent="app_error",
    service_name="aiops-demo-service"
)

# Get time window
state = scout.investigate(state)

# Collect logs
state = collector.investigate(state)

print(f"\nFound {len(state.log_evidence)} logs")
print("\nFirst 5 log messages:")
for i, log in enumerate(state.log_evidence[:5], 1):
    print(f"\n{i}. Severity: {log.severity}")
    print(f"   Message: {log.message[:200]}")