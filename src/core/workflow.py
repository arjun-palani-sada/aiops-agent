"""
Sequential Workflow Engine

Manages the sequential execution of investigation agents.
Ensures agents run in strict order with proper state passing.
"""

import logging
from typing import List, Callable, Optional

from .state import InvestigationState


class SequentialWorkflow:
    """
    Executes agents in a fixed sequence.

    This prevents LLM loops by enforcing strict order:
    Metric Scout → Log Collector → Analyst → [Infra Detective]
    """

    def __init__(self, agents: List[tuple]):
        """
        Initialize workflow with agents

        Args:
            agents: List of (name, agent_instance, is_conditional) tuples
        """
        self.agents = agents
        self.logger = logging.getLogger(self.__class__.__name__)

    def execute(
            self,
            state: InvestigationState
    ) -> InvestigationState:
        """
        Execute all agents in sequence

        Args:
            state: Initial investigation state

        Returns:
            Final state after all agents have processed
        """
        self.logger.info("Starting sequential workflow")

        for name, agent, is_conditional in self.agents:
            try:
                # Check if this is a conditional agent
                if is_conditional:
                    should_run = self._should_run_conditional(state, name)
                    if not should_run:
                        self.logger.info(f"Skipping {name} (condition not met)")
                        continue

                self.logger.info(f"Running {name}")

                # Execute the agent
                state = agent.investigate(state)

                # Validate state has required fields for next agent
                if not self._validate_state(state, name):
                    self.logger.warning(f"{name} did not produce required output")
                    # Continue anyway - let next agents handle it

            except Exception as e:
                error_msg = f"Error in {name}: {str(e)}"
                self.logger.error(error_msg)
                state.add_error(error_msg)
                # Continue with workflow despite error

        self.logger.info("Sequential workflow complete")
        return state

    def _should_run_conditional(
            self,
            state: InvestigationState,
            agent_name: str
    ) -> bool:
        """
        Determine if conditional agent should run

        Args:
            state: Current state
            agent_name: Name of conditional agent

        Returns:
            True if agent should run
        """
        if agent_name == "infra_detective":
            # Run if analyst flagged infrastructure issues
            if state.root_cause_analysis:
                return state.root_cause_analysis.requires_infra_check
            return False

        # Default: run the agent
        return True

    def _validate_state(
            self,
            state: InvestigationState,
            agent_name: str
    ) -> bool:
        """
        Validate state has required outputs

        Args:
            state: Current state
            agent_name: Name of agent that just ran

        Returns:
            True if state is valid
        """
        validations = {
            "metric_scout": lambda s: s.time_window is not None,
            "log_collector": lambda s: s.log_evidence is not None,
            "analyst": lambda s: True,  # Always valid (can produce None)
            "infra_detective": lambda s: s.infrastructure_findings is not None,
        }

        validator = validations.get(agent_name)
        if validator:
            return validator(state)

        return True  # Unknown agent, assume valid


class WorkflowBuilder:
    """Helper class to build workflows"""

    @staticmethod
    def create_investigation_workflow(
            metric_scout,
            log_collector,
            analyst,
            infra_detective
    ) -> SequentialWorkflow:
        """
        Create the standard investigation workflow

        Args:
            metric_scout: MetricScout instance
            log_collector: LogCollector instance
            analyst: Analyst instance
            infra_detective: InfraDetective instance

        Returns:
            Configured SequentialWorkflow
        """
        agents = [
            ("metric_scout", metric_scout, False),
            ("log_collector", log_collector, False),
            ("analyst", analyst, False),
            ("infra_detective", infra_detective, True),  # Conditional
        ]

        return SequentialWorkflow(agents)


if __name__ == "__main__":
    import os
    from ..core import StateManager
    from ..agents import (
        MetricScout, LogCollector, Analyst,
        InfraDetective, Summarizer
    )
    from ..mcp import GCPMonitoringServer, GCPLoggingServer

    logging.basicConfig(level=logging.INFO)

    project_id = os.environ.get("GCP_PROJECT_ID", "demo-project")

    # Initialize MCP servers
    monitoring = GCPMonitoringServer(project_id)
    logging_server = GCPLoggingServer(project_id)

    # Initialize agents
    metric_scout = MetricScout(monitoring)
    log_collector = LogCollector(logging_server)
    analyst = Analyst(use_llm=False)
    infra_detective = InfraDetective(logging_server)
    summarizer = Summarizer(use_llm=False)

    # Build workflow
    workflow = WorkflowBuilder.create_investigation_workflow(
        metric_scout=metric_scout,
        log_collector=log_collector,
        analyst=analyst,
        infra_detective=infra_detective
    )

    # Create initial state
    state = StateManager.create_initial_state(
        intent="app_crash",
        service_name="demo-app",
        user_query="My app is crashing, help!"
    )

    print("\n" + "=" * 60)
    print("Testing Sequential Workflow Engine")
    print("=" * 60)

    # Execute workflow
    print("\n🔄 Executing workflow...")
    state = workflow.execute(state)

    # Complete investigation
    state.complete_investigation()

    # Summarize
    print("\n📊 Generating summary...")
    summary = summarizer.summarize(state)

    print("\n" + summary)

    # Print workflow statistics
    print("\n" + "=" * 60)
    print("Workflow Statistics")
    print("=" * 60)
    print(f"Agents executed: {len(state.agent_sequence)}")
    print(f"Duration: {state.get_duration_seconds():.2f}s")
    print(f"Errors: {len(state.errors)}")
    print(f"\nAgent sequence:")
    for i, agent_step in enumerate(state.agent_sequence, 1):
        print(f"  {i}. {agent_step}")