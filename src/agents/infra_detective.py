"""
Infra Detective Agent (Step 2d)

Investigates infrastructure issues (permissions, network).
Runs conditionally when Analyst determines infrastructure is involved.
"""

import logging
from typing import Optional

from ..core.state import InvestigationState, InfrastructureFindings
from ..mcp.gcp_logging import GCPLoggingServer


class InfraDetective:
    """
    Agent that investigates infrastructure issues.

    Checks for:
    - Permission denied errors
    - Network connectivity issues
    - Firewall blocks
    """

    def __init__(self, logging_server: GCPLoggingServer):
        """
        Initialize Infra Detective

        Args:
            logging_server: GCP Logging MCP server
        """
        self.logging = logging_server
        self.logger = logging.getLogger(self.__class__.__name__)

    def investigate(
            self,
            state: InvestigationState,
            max_logs: int = 100
    ) -> InvestigationState:
        """
        Investigate infrastructure issues

        Args:
            state: Investigation state with root cause analysis
            max_logs: Maximum audit logs to fetch

        Returns:
            Updated state with infrastructure_findings
        """
        self.logger.info(f"Investigating infrastructure for {state.service_name}")
        state.add_agent_step("infra_detective")

        if not state.time_window:
            error_msg = "No time window available"
            self.logger.error(error_msg)
            state.add_error(error_msg)
            return state

        findings = InfrastructureFindings()

        try:
            # Check audit logs for permission errors
            findings.permission_errors = self._check_permissions(state, max_logs)

            # Check for network issues
            findings.network_errors = self._check_network(state, max_logs)

            # Check VPC flow logs for firewall issues
            findings.firewall_issues = self._check_firewall(state, max_logs)

            state.infrastructure_findings = findings

            total_issues = (
                    len(findings.permission_errors) +
                    len(findings.network_errors) +
                    len(findings.firewall_issues)
            )

            self.logger.info(f"Found {total_issues} infrastructure issues")

        except Exception as e:
            error_msg = f"Infrastructure investigation error: {str(e)}"
            self.logger.error(error_msg)
            state.add_error(error_msg)

        return state

    def _check_permissions(
            self,
            state: InvestigationState,
            max_logs: int
    ) -> list:
        """Check audit logs for permission errors"""
        try:
            result = self.logging.list_audit_logs(
                resource_type="cloud_run_revision",
                time_range={
                    "start": state.time_window.start,
                    "end": state.time_window.end
                },
                max_entries=max_logs
            )

            if result.get("success"):
                logs = result.get("logs", [])

                # Find permission-related errors
                permission_errors = []
                for log in logs:
                    message = str(log.get("message", "")).lower()
                    if any(word in message for word in [
                        "permission", "denied", "unauthorized",
                        "forbidden", "iam", "access"
                    ]):
                        permission_errors.append(message[:200])

                return permission_errors[:5]  # Top 5

        except Exception as e:
            self.logger.warning(f"Failed to check permissions: {e}")

        return []

    def _check_network(
            self,
            state: InvestigationState,
            max_logs: int
    ) -> list:
        """Check for network connectivity issues"""
        try:
            # Build filter for network-related logs
            filter_str = (
                f'resource.type="cloud_run_revision" AND '
                f'resource.labels.service_name="{state.service_name}" AND '
                f'timestamp>="{state.time_window.start}" AND '
                f'timestamp<="{state.time_window.end}" AND '
                f'(textPayload=~"connection" OR textPayload=~"timeout" OR textPayload=~"network")'
            )

            result = self.logging.list_entries(
                filter_str=filter_str,
                max_entries=max_logs
            )

            if result.get("success"):
                logs = result.get("logs", [])

                network_errors = []
                for log in logs:
                    message = str(log.get("message", ""))
                    network_errors.append(message[:200])

                return network_errors[:5]  # Top 5

        except Exception as e:
            self.logger.warning(f"Failed to check network: {e}")

        return []

    def _check_firewall(
            self,
            state: InvestigationState,
            max_logs: int
    ) -> list:
        """Check VPC flow logs for firewall blocks"""
        try:
            # Build filter for VPC flow logs
            filter_str = (
                f'resource.type="gce_subnetwork" AND '
                f'timestamp>="{state.time_window.start}" AND '
                f'timestamp<="{state.time_window.end}" AND '
                f'(jsonPayload.connection.disposition="BLOCKED" OR '
                f'jsonPayload.connection.disposition="REJECTED")'
            )

            result = self.logging.list_entries(
                filter_str=filter_str,
                max_entries=max_logs
            )

            if result.get("success"):
                logs = result.get("logs", [])

                firewall_issues = []
                for log in logs:
                    message = f"Firewall block: {log.get('message', 'Unknown')}"
                    firewall_issues.append(message[:200])

                return firewall_issues[:5]  # Top 5

        except Exception as e:
            self.logger.warning(f"Failed to check firewall: {e}")

        return []


if __name__ == "__main__":
    import os
    from ..core import StateManager
    from ..agents.metric_scout import MetricScout
    from ..agents.log_collector import LogCollector
    from ..agents.analyst import Analyst
    from ..mcp import GCPMonitoringServer, GCPLoggingServer

    logging.basicConfig(level=logging.INFO)

    project_id = os.environ.get("GCP_PROJECT_ID", "demo-project")

    # Setup all agents
    monitoring = GCPMonitoringServer(project_id)
    logging_server = GCPLoggingServer(project_id)

    scout = MetricScout(monitoring)
    collector = LogCollector(logging_server)
    analyst = Analyst(use_llm=False)
    detective = InfraDetective(logging_server)

    # Run full workflow with conditional Infra Detective
    state = StateManager.create_initial_state(
        intent="app_crash",
        service_name="demo-app"
    )

    print("\n" + "=" * 60)
    print("Running 4-Step Investigation Workflow")
    print("=" * 60)

    # Step 1: Find time window
    print("\n1. Metric Scout - Finding time window...")
    state = scout.investigate(state)
    print(f"   ✅ Time window found")

    # Step 2: Collect logs
    print("\n2. Log Collector - Fetching logs...")
    state = collector.investigate(state)
    print(f"   ✅ Logs collected: {len(state.log_evidence)}")

    # Step 3: Analyze
    print("\n3. Analyst - Determining root cause...")
    state = analyst.investigate(state)

    # Step 4: Conditional - Run Infra Detective if needed
    if state.root_cause_analysis and state.root_cause_analysis.requires_infra_check:
        print("\n4. Infra Detective - Checking infrastructure...")
        state = detective.investigate(state)

        if state.infrastructure_findings:
            print(f"   ✅ Permission errors: {len(state.infrastructure_findings.permission_errors)}")
            print(f"   ✅ Network errors: {len(state.infrastructure_findings.network_errors)}")
            print(f"   ✅ Firewall issues: {len(state.infrastructure_findings.firewall_issues)}")
    else:
        print("\n4. Infra Detective - Skipped (not required)")

    # Complete the investigation
    state.complete_investigation()

    print("\n" + "=" * 60)
    print("Investigation Complete!")
    print("=" * 60)
    print(f"Agent sequence: {' → '.join(state.agent_sequence)}")
    print(f"Duration: {state.get_duration_seconds():.2f}s")