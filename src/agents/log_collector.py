"""
Log Collector Agent (Step 2b) - IMPROVED VERSION

Fetches relevant logs for the identified time window.
IMPROVED: Better message extraction from Cloud Run logs
"""

import logging
from typing import Optional
import json

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
                
                # Convert to LogEntry objects with IMPROVED message extraction
                for log in logs:
                    message = self._extract_message(log)
                    
                    # Only add logs with actual content
                    if message and message.strip():
                        state.log_evidence.append(LogEntry(
                            timestamp=log.get("timestamp", ""),
                            severity=log.get("severity", "UNKNOWN"),
                            message=message,
                            resource=log.get("resource"),
                            labels=log.get("labels")
                        ))
                
                # Create summary
                error_count = sum(
                    1 for log in state.log_evidence
                    if log.severity in ["ERROR", "CRITICAL"]
                )
                
                state.log_summary = (
                    f"Collected {len(state.log_evidence)} logs "
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
    
    def _extract_message(self, log: dict) -> str:
        """
        IMPROVED: Extract message from Cloud Run log entry
        
        Cloud Run logs can have messages in different fields:
        - textPayload: Direct text message
        - jsonPayload.message: Structured log message
        - httpRequest: HTTP request info (for access logs)
        
        Args:
            log: Raw log entry dict
            
        Returns:
            Extracted message string
        """
        # Try textPayload first (most common)
        if "message" in log:
            if isinstance(log["message"], str):
                return log["message"]
            elif isinstance(log["message"], dict):
                # Sometimes message is a dict, try to get useful fields
                if "message" in log["message"]:
                    return str(log["message"]["message"])
                # Convert dict to readable string
                return json.dumps(log["message"])
        
        # Try direct string conversion (fallback)
        if log.get("message"):
            return str(log["message"])
        
        # For HTTP request logs, construct meaningful message
        # These have status codes but no textPayload
        http_info = []
        
        # Check if this is an HTTP request log
        resource = log.get("resource", {})
        if resource.get("type") == "cloud_run_revision":
            severity = log.get("severity", "")
            
            # Map severity to likely issues
            if severity == "WARNING":
                http_info.append("HTTP request resulted in warning status")
            elif severity == "ERROR":
                http_info.append("HTTP request resulted in error status")
            
            # Note: We can't see the actual status code from the MCP response
            # but we know it's a WARNING/ERROR log
            
            return " ".join(http_info) if http_info else "Cloud Run service log entry"
        
        # Last resort: return a generic message
        return f"Log entry with severity {log.get('severity', 'UNKNOWN')}"


# Example usage
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
    
    print("\nRunning Log Collection Test:")
    print("="*60)
    
    # Step 1: Find time window
    print("\n1. Metric Scout - Finding time window...")
    state = scout.investigate(state)
    print(f"   ✅ Time window: {state.time_window.start}")
    
    # Step 2: Collect logs
    print("\n2. Log Collector - Fetching logs...")
    state = collector.investigate(state)
    print(f"   ✅ Logs collected: {len(state.log_evidence)}")
    
    # Show first 5 messages
    print("\nFirst 5 log messages:")
    for i, log in enumerate(state.log_evidence[:5], 1):
        print(f"\n{i}. [{log.severity}] {log.message[:150]}")
    
    print("\n" + "="*60)
    print("Log collection complete!")
