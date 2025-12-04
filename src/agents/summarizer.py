"""
Summarizer Agent (Agent 3)

Translates technical findings into user-friendly explanations.
"""

import logging
from typing import Optional
from ..config import Config

from ..core.state import InvestigationState

class Summarizer:
    """
    Agent that creates user-friendly summaries.

    Converts technical jargon and stack traces into plain English
    that anyone can understand.
    """

    def __init__(self, use_llm: bool = True):
        """
        Initialize Summarizer

        Args:
            use_llm: Whether to use actual LLM for summarization
                    If False, uses template-based summarization
        """
        self.use_llm = use_llm
        self.logger = logging.getLogger(self.__class__.__name__)

        if use_llm:
            try:
                import google.generativeai as genai
                import os

                api_key = Config.get_google_api_key()
                model_name = Config.get_model_name()
                if api_key:
                    genai.configure(api_key=api_key)
                    self.model = genai.GenerativeModel(model_name)
                    self.logger.info("Using Gemini LLM for summarization")
                else:
                    self.logger.warning("No GOOGLE_API_KEY, using template-based")
                    self.use_llm = False
            except ImportError:
                self.logger.warning("google-generativeai not installed, using templates")
                self.use_llm = False

    def summarize(self, state: InvestigationState) -> str:
        """
        Create user-friendly summary of the investigation

        Args:
            state: Complete investigation state

        Returns:
            Human-readable summary
        """
        self.logger.info(f"Summarizing investigation for {state.service_name}")

        if self.use_llm:
            return self._summarize_with_llm(state)
        else:
            return self._summarize_with_template(state)

    def _summarize_with_template(self, state: InvestigationState) -> str:
        """Template-based summarization (no LLM required)"""

        lines = []

        # Header
        lines.append("=" * 60)
        lines.append(f"Investigation Summary: {state.service_name}")
        lines.append("=" * 60)

        # Time window
        if state.time_window:
            lines.append(f"\n📅 Issue occurred between:")
            lines.append(f"   {state.time_window.start}")
            lines.append(f"   and {state.time_window.end}")

        # Root cause
        if state.root_cause_analysis:
            rca = state.root_cause_analysis

            lines.append(f"\n🔍 What happened:")
            lines.append(f"   {rca.description}")

            lines.append(f"\n📊 Confidence: {rca.confidence:.0%}")

            # Issue type
            issue_type_friendly = {
                "code_error": "Application Code Error",
                "infrastructure": "Infrastructure Issue",
                "network": "Network Connectivity Problem",
                "permissions": "Permission/Authorization Issue",
                "resource_exhaustion": "Resource Limit Reached",
                "unknown": "Unable to Determine"
            }

            lines.append(f"\n⚠️  Issue Type: {issue_type_friendly.get(rca.root_cause_type.value, 'Unknown')}")

        # Evidence summary
        lines.append(f"\n📋 Evidence collected:")
        lines.append(f"   • {len(state.metrics)} metrics analyzed")
        lines.append(f"   • {len(state.log_evidence)} log entries examined")

        if state.time_window and state.time_window.anomaly_detected:
            lines.append(f"   • ⚠️  Anomalies detected in metrics")

        # Infrastructure findings
        if state.infrastructure_findings:
            findings = state.infrastructure_findings

            if findings.permission_errors:
                lines.append(f"\n🔒 Permission Issues Found:")
                for error in findings.permission_errors[:3]:
                    lines.append(f"   • {error[:100]}")

            if findings.network_errors:
                lines.append(f"\n🌐 Network Issues Found:")
                for error in findings.network_errors[:3]:
                    lines.append(f"   • {error[:100]}")

            if findings.firewall_issues:
                lines.append(f"\n🔥 Firewall Blocks Found:")
                for issue in findings.firewall_issues[:3]:
                    lines.append(f"   • {issue[:100]}")

        # Recommendations
        lines.append(f"\n💡 Recommended Actions:")

        if state.root_cause_analysis:
            rca = state.root_cause_analysis

            if rca.root_cause_type.value == "code_error":
                lines.append("   1. Review recent code changes")
                lines.append("   2. Check error logs for stack traces")
                lines.append("   3. Test in staging environment")

            elif rca.root_cause_type.value == "permissions":
                lines.append("   1. Verify IAM permissions")
                lines.append("   2. Check service account configuration")
                lines.append("   3. Review audit logs")

            elif rca.root_cause_type.value == "network":
                lines.append("   1. Check network connectivity")
                lines.append("   2. Verify firewall rules")
                lines.append("   3. Test external service endpoints")

            elif rca.root_cause_type.value == "resource_exhaustion":
                lines.append("   1. Increase resource limits")
                lines.append("   2. Optimize resource usage")
                lines.append("   3. Consider auto-scaling")

            elif rca.root_cause_type.value == "infrastructure":
                lines.append("   1. Contact infrastructure team")
                lines.append("   2. Check dependent services")
                lines.append("   3. Review service health dashboards")

            else:
                lines.append("   1. Review all collected logs")
                lines.append("   2. Escalate to on-call engineer")
                lines.append("   3. Run deeper diagnostics")

        # Duration
        if state.get_duration_seconds():
            lines.append(f"\n⏱️  Investigation completed in {state.get_duration_seconds():.2f}s")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)

    def _summarize_with_llm(self, state: InvestigationState) -> str:
        """LLM-based summarization using Gemini"""

        summary_dict = state.to_summary_dict()

        prompt = f"""You are an expert SRE creating a clear, friendly summary for engineers.

Investigation Results:
{summary_dict}

Create a clear, actionable summary that:
1. Explains what happened in simple terms
2. States the root cause clearly
3. Provides 3 concrete next steps
4. Uses friendly, professional tone

Keep it concise (under 300 words).
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            self.logger.error(f"LLM summarization failed: {e}, using template")
            return self._summarize_with_template(state)


if __name__ == "__main__":
    import os
    from ..core import StateManager
    from .metric_scout import MetricScout
    from .log_collector import LogCollector
    from .analyst import Analyst
    from .infra_detective import InfraDetective
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
    summarizer = Summarizer(use_llm=False)

    # Run COMPLETE workflow
    state = StateManager.create_initial_state(
        intent="app_crash",
        service_name="demo-app",
        user_query="Why is my app crashing?"
    )

    print("\n🔍 Starting Investigation...")

    # Sequential workflow
    state = scout.investigate(state)
    state = collector.investigate(state)
    state = analyst.investigate(state)

    # Conditional: Run infra detective if needed
    if state.root_cause_analysis and state.root_cause_analysis.requires_infra_check:
        state = detective.investigate(state)

    # Complete and summarize
    state.complete_investigation()
    summary = summarizer.summarize(state)

    # Display summary
    print("\n" + summary)