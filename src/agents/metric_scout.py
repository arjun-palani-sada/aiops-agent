"""
Metric Scout Agent (Step 2a)

Finds precise time window where anomalies occurred.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from ..core.state import InvestigationState, TimeWindow, MetricData
from ..mcp.gcp_monitoring import GCPMonitoringServer


class MetricScout:
    """
    Agent that identifies the exact time window for investigation.

    For high-traffic apps: Detects anomalies
    For low-traffic apps: Finds exact error timestamps
    """

    def __init__(self, monitoring_server: GCPMonitoringServer):
        """
        Initialize Metric Scout

        Args:
            monitoring_server: GCP Monitoring MCP server
        """
        self.monitoring = monitoring_server
        self.logger = logging.getLogger(self.__class__.__name__)

    def investigate(
            self,
            state: InvestigationState,
            lookback_hours: int = 24
    ) -> InvestigationState:
        """
        Find time window with anomalies

        Args:
            state: Current investigation state
            lookback_hours: Hours to look back for baseline

        Returns:
            Updated state with time_window and metrics
        """
        self.logger.info(f"Starting investigation for {state.service_name}")
        state.add_agent_step("metric_scout")

        try:
            # Detect anomalies in CPU usage
            result = self.monitoring.detect_anomalies(
                metric_type="run.googleapis.com/container/cpu/utilization",
                resource_type="cloud_run_revision",
                service_name=state.service_name,
                lookback_hours=lookback_hours
            )

            if result.get("success") and result.get("anomaly_count", 0) > 0:
                # High-traffic mode: Found anomalies
                self._process_anomalies(state, result)
            else:
                # Low-traffic mode: Use default recent window
                self._use_default_window(state)

            self.logger.info(
                f"Time window: {state.time_window.start} to {state.time_window.end}"
            )

        except Exception as e:
            self.logger.error(f"Error in investigation: {e}")
            state.add_error(f"MetricScout error: {str(e)}")
            self._use_default_window(state)

        return state

    def _process_anomalies(
            self,
            state: InvestigationState,
            result: dict
    ) -> None:
        """Process detected anomalies"""
        anomalies = result.get("anomalies", [])

        if not anomalies:
            return

        # Get time range from first to last anomaly
        first_anomaly = anomalies[0]
        last_anomaly = anomalies[-1]

        state.time_window = TimeWindow(
            start=first_anomaly["timestamp"],
            end=last_anomaly["timestamp"],
            anomaly_detected=True,
            confidence=0.9
        )

        # Add metric data
        for anomaly in anomalies[:10]:  # Top 10 anomalies
            state.metrics.append(MetricData(
                metric_type="cpu_utilization",
                value=anomaly["value"],
                timestamp=anomaly["timestamp"],
                is_anomalous=True,
                threshold=anomaly.get("baseline_mean", 0)
            ))

        self.logger.info(f"Found {len(anomalies)} anomalies")

    def _use_default_window(self, state: InvestigationState) -> None:
        """Use default time window when no anomalies found"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=15)

        state.time_window = TimeWindow(
            start=start_time.isoformat() + 'Z',
            end=end_time.isoformat() + 'Z',
            anomaly_detected=False,
            confidence=0.5
        )

        self.logger.info("Using default 15-minute window")


if __name__ == "__main__":
    import os
    from ..core import StateManager

    logging.basicConfig(level=logging.INFO)

    project_id = os.environ.get("GCP_PROJECT_ID", "demo-project")

    # Setup
    monitoring = GCPMonitoringServer(project_id)
    scout = MetricScout(monitoring)

    # Create test state
    state = StateManager.create_initial_state(
        intent="app_crash",
        service_name="demo-app"
    )

    # Run investigation
    updated_state = scout.investigate(state)

    print(f"\n{'=' * 60}")
    print("Metric Scout Results:")
    print('=' * 60)
    print(f"  Service: {updated_state.service_name}")
    print(f"  Time window: {updated_state.time_window.start}")
    print(f"               to {updated_state.time_window.end}")
    print(f"  Anomaly detected: {updated_state.time_window.anomaly_detected}")
    print(f"  Metrics found: {len(updated_state.metrics)}")
    print(f"  Confidence: {updated_state.time_window.confidence}")
    print('=' * 60)