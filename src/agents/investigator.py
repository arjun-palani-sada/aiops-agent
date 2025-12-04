"""
Investigator Agent (Agent 2)

Orchestrates the sequential investigation workflow.
Wraps the 4-step process as a single "tool" for the root agent.
"""

import logging
from typing import Dict, Any

from ..core.state import InvestigationState, StateManager
from ..core.workflow import SequentialWorkflow, WorkflowBuilder
from ..agents import (
    MetricScout, LogCollector, Analyst,
    InfraDetective, Summarizer
)
from ..mcp import GCPMonitoringServer, GCPLoggingServer


class Investigator:
    """
    Agent 2: The Sequential Workflow Engine

    This is the "black box" that the root orchestrator calls.
    It manages the entire 4-step investigation process internally.
    """

    def __init__(
            self,
            project_id: str,
            use_llm: bool = False
    ):
        """
        Initialize Investigator with all sub-agents

        Args:
            project_id: GCP project ID
            use_llm: Whether to use LLM for Analyst and Summarizer
        """
        self.project_id = project_id
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize MCP servers
        self.monitoring = GCPMonitoringServer(project_id)
        self.logging_server = GCPLoggingServer(project_id)

        # Initialize all agents
        self.metric_scout = MetricScout(self.monitoring)
        self.log_collector = LogCollector(self.logging_server)
        self.analyst = Analyst(use_llm=use_llm)
        self.infra_detective = InfraDetective(self.logging_server)
        self.summarizer = Summarizer(use_llm=use_llm)

        # Build the workflow
        self.workflow = WorkflowBuilder.create_investigation_workflow(
            metric_scout=self.metric_scout,
            log_collector=self.log_collector,
            analyst=self.analyst,
            infra_detective=self.infra_detective
        )

        self.logger.info("Investigator initialized")

    def investigate_app_health(
            self,
            service_name: str,
            intent: str = "app_error",
            user_query: str = ""
    ) -> Dict[str, Any]:
        """
        Investigate application health issues

        This is the single function that the root orchestrator calls.
        It runs the entire 4-step workflow and returns a summary.

        Args:
            service_name: Name of the service to investigate
            intent: Type of issue (app_crash, app_error, performance_issue)
            user_query: Original user query

        Returns:
            Dict with investigation results and summary
        """
        self.logger.info(f"Starting investigation for {service_name}")

        try:
            # Create initial state
            state = StateManager.create_initial_state(
                intent=intent,
                service_name=service_name,
                user_query=user_query
            )

            # Execute the sequential workflow
            state = self.workflow.execute(state)

            # Complete the investigation
            state.complete_investigation()

            # Generate user-friendly summary
            summary = self.summarizer.summarize(state)

            # Return results
            return {
                "success": True,
                "service_name": service_name,
                "summary": summary,
                "root_cause": (
                    state.root_cause_analysis.description
                    if state.root_cause_analysis
                    else "Unable to determine"
                ),
                "confidence": (
                    state.root_cause_analysis.confidence
                    if state.root_cause_analysis
                    else 0.0
                ),
                "time_window": {
                    "start": state.time_window.start if state.time_window else None,
                    "end": state.time_window.end if state.time_window else None,
                },
                "metrics_analyzed": len(state.metrics),
                "logs_analyzed": len(state.log_evidence),
                "duration_seconds": state.get_duration_seconds(),
                "agent_sequence": state.agent_sequence,
                "errors": state.errors,
            }

        except Exception as e:
            self.logger.error(f"Investigation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_name": service_name,
            }

    def get_tool_definition(self) -> Dict[str, Any]:
        """
        Get the tool definition for the root orchestrator

        Returns:
            Tool definition dict
        """
        return {
            "name": "investigate_app_health",
            "description": (
                "Investigate application health issues, errors, and crashes. "
                "Analyzes metrics, logs, and infrastructure to determine root cause. "
                "Use this for any reports of application problems."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to investigate"
                    },
                    "intent": {
                        "type": "string",
                        "description": "Type of issue (app_crash, app_error, performance_issue)",
                        "default": "app_error"
                    },
                    "user_query": {
                        "type": "string",
                        "description": "Original user query or issue description"
                    }
                },
                "required": ["service_name"]
            }
        }


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO)

    project_id = os.environ.get("GCP_PROJECT_ID", "demo-project")

    # Initialize Investigator
    investigator = Investigator(project_id=project_id, use_llm=False)

    print("\n" + "=" * 60)
    print("Testing Investigator Agent (Agent 2)")
    print("=" * 60)

    # Test case 1: App crash
    print("\n📋 Test Case 1: App Crash Investigation")
    print("-" * 60)

    result = investigator.investigate_app_health(
        service_name="demo-app",
        intent="app_crash",
        user_query="My app is crashing when users try to login!"
    )

    if result["success"]:
        print(f"\n✅ Investigation completed successfully")
        print(f"\nService: {result['service_name']}")
        print(f"Root Cause: {result['root_cause']}")
        print(f"Confidence: {result['confidence']:.0%}")
        print(f"Metrics Analyzed: {result['metrics_analyzed']}")
        print(f"Logs Analyzed: {result['logs_analyzed']}")
        print(f"Duration: {result['duration_seconds']:.2f}s")
        print(f"\nFull Summary:")
        print(result['summary'])
    else:
        print(f"\n❌ Investigation failed: {result.get('error')}")

    # Test case 2: Performance issue
    print("\n" + "=" * 60)
    print("\n📋 Test Case 2: Performance Issue")
    print("-" * 60)

    result2 = investigator.investigate_app_health(
        service_name="api-service",
        intent="performance_issue",
        user_query="API is very slow, taking 10+ seconds to respond"
    )

    if result2["success"]:
        print(f"\n✅ Investigation completed")
        print(f"Duration: {result2['duration_seconds']:.2f}s")
        print(f"Agents executed: {len(result2['agent_sequence'])}")

    # Test the tool definition
    print("\n" + "=" * 60)
    print("\n🔧 Tool Definition (for Root Orchestrator)")
    print("-" * 60)

    import json

    tool_def = investigator.get_tool_definition()
    print(json.dumps(tool_def, indent=2))

    print("\n" + "=" * 60)
    print("✅ Investigator Agent Ready!")
    print("=" * 60)
    print("\nThis agent can now be used as a tool by the Ops Commander.")
    print("It wraps the entire 4-step workflow in a single function call.")