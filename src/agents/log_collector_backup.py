"""
Log Collector Agent (Step 2b)

Fetches relevant logs for the identified time window.
"""

import logging
from typing import Optional

from ..core.state import InvestigationState, LogEntry
from ..core.utils import format_log_filter
from ..mcp.gcp_logging import GCPLoggingServer


class LogCollector:
    """Agent that collects log evidence for analysis"""

    def __init__(self, logging_server: GCPLoggingServer):
        """
        Initialize Log Collector

        Args:
            logging_server: GCP Logging MCP server
        """
        self.logging = logging_server
        self.logger = logging.getLogger(self.__class__.__name__)

    def investigate(
            self,
            state: InvestigationState,
            max_logs: int = 500
    ) -> InvestigationState:
        """
        Collect logs for the investigation time window

        Args:
            state: Investigation state with time_window set
            max_logs: Maximum number of logs to collect

        Returns:
            Updated state with log_evidence
        """
        self.logger.info(f"Collecting logs for {state.service_name}")
        state.add_agent_step("log_collector")

        if not state.time_window:
            error_msg = "No time window available for log collection"
            self.logger.error(error_msg)
            state.add_error(error_msg)
            return state

        try:
            # Build log filter
            log_filter = format_log_filter(
                resource_type="cloud_run_revision",
                severity="WARNING",
                time_range={
                    "start": state.time_window.start,
                    "end": state.time_window.end
                },
                service_name=state.service_name
            )

            self.logger.info(f"Using filter: {log_filter}")

            # Fetch logs
            result = self.logging.list_entries(
                filter_str=log_filter,
                max_entries=max_logs
            )

            if result.get("success"):
                logs = result.get("logs", [])

                # Convert to LogEntry objects
                for log in logs:
                    state.log_evidence.append(LogEntry(
                        timestamp=log.get("timestamp", ""),
                        severity=log.get("severity", "UNKNOWN"),
                        message=str(log.get("message", "")),
                        resource=log.get("resource"),
                        labels=log.get("labels")
                    ))

                # Create summary
                error_count = sum(
                    1 for log in logs
                    if log.get("severity") == "ERROR"
                )
                state.log_summary = (
                    f"Collected {len(logs)} logs "
                    f"({error_count} errors) "
                    f"from {state.time_window.start}"
                )

                self.logger.info(state.log_summary)
            else:
                error_msg = f"Failed to fetch logs: {result.get('error')}"
                self.logger.error(error_msg)
                state.add_error(error_msg)

        except Exception as e:
            error_msg = f"Error collecting logs: {str(e)}"
            self.logger.error(error_msg)
            state.add_error(error_msg)

        return state


if __name__ == "__main__":
    import os
    from ..core import StateManager
    from ..agents.metric_scout import MetricScout
    from ..mcp import GCPMonitoringServer

    logging.basicConfig(level=logging.INFO)

    project_id = os.environ.get("GCP_PROJECT_ID", "demo-project")

    # Setup
    monitoring = GCPMonitoringServer(project_id)
    logging_server = GCPLoggingServer(project_id)

    scout = MetricScout(monitoring)
    collector = LogCollector(logging_server)

    # Create and run workflow
    state = StateManager.create_initial_state(
        intent="app_crash",
        service_name="demo-app"
    )

    print("\nRunning Sequential Workflow:")
    print("=" * 60)

    # Step 1: Find time window
    print("\n1. Metric Scout - Finding time window...")
    state = scout.investigate(state)
    print(f"   ✅ Time window: {state.time_window.start}")

    # Step 2: Collect logs
    print("\n2. Log Collector - Fetching logs...")
    state = collector.investigate(state)
    print(f"   ✅ Logs collected: {len(state.log_evidence)}")

    print("\n" + "=" * 60)
    print("Workflow Complete!")
    print("=" * 60)
    print(f"Summary: {state.log_summary}")