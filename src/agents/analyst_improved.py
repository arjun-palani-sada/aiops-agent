"""
Analyst Agent (Step 2c) - IMPROVED VERSION

Correlates metrics and logs to determine root cause.
This version works well even with logs-only (no metrics).
"""

import logging
from typing import Optional
import json

from ..core.state import InvestigationState, RootCauseAnalysis, RootCauseType
from ..core.utils import extract_error_patterns


class Analyst:
    """
    Agent that performs root cause analysis.
    
    Uses LLM reasoning to correlate metrics with log evidence.
    IMPROVED: Can analyze logs even when metrics are missing.
    """
    
    def __init__(self, use_llm: bool = False):
        """
        Initialize Analyst
        
        Args:
            use_llm: Whether to use actual LLM (requires Gemini API)
                    If False, uses rule-based analysis
        """
        self.use_llm = use_llm
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if use_llm:
            try:
                import google.generativeai as genai
                import os
                
                api_key = os.environ.get("GOOGLE_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    self.model = genai.GenerativeModel('gemini-1.5-flash')
                    self.logger.info("Using Gemini LLM for analysis")
                else:
                    self.logger.warning("No GOOGLE_API_KEY found, falling back to rule-based")
                    self.use_llm = False
            except ImportError:
                self.logger.warning("google-generativeai not installed, using rule-based")
                self.use_llm = False
    
    def investigate(
        self,
        state: InvestigationState
    ) -> InvestigationState:
        """
        Analyze metrics and logs to determine root cause
        
        Args:
            state: Investigation state with metrics and logs
            
        Returns:
            Updated state with root_cause_analysis
        """
        self.logger.info(f"Analyzing evidence for {state.service_name}")
        state.add_agent_step("analyst")
        
        # IMPROVED: Only require logs (metrics are optional)
        if not state.log_evidence or len(state.log_evidence) == 0:
            error_msg = "No logs available for analysis"
            self.logger.warning(error_msg)
            state.add_error(error_msg)
            return state
        
        try:
            if self.use_llm:
                analysis = self._analyze_with_llm(state)
            else:
                analysis = self._analyze_with_rules(state)
            
            state.root_cause_analysis = analysis
            
            self.logger.info(
                f"Root cause: {analysis.root_cause_type.value} "
                f"(confidence: {analysis.confidence:.2f})"
            )
            
        except Exception as e:
            error_msg = f"Analysis error: {str(e)}"
            self.logger.error(error_msg)
            state.add_error(error_msg)
        
        return state
    
    def _analyze_with_rules(
        self,
        state: InvestigationState
    ) -> RootCauseAnalysis:
        """
        IMPROVED rule-based analysis
        
        Works well even with logs-only (no metrics)
        """
        # Extract error patterns from logs
        error_patterns = extract_error_patterns([
            {"message": log.message} for log in state.log_evidence
        ])
        
        # Check metrics for resource issues (if available)
        high_cpu = False
        if state.metrics:
            high_cpu = any(
                m.value > 80 and m.is_anomalous 
                for m in state.metrics
            )
        
        # Analyze log messages
        log_messages = " ".join([log.message for log in state.log_evidence[:20]])
        log_messages_lower = log_messages.lower()
        
        # Count error types
        error_counts = {}
        for log in state.log_evidence:
            msg_lower = log.message.lower()
            severity = log.severity
            
            if any(word in msg_lower for word in ["permission", "denied", "unauthorized", "forbidden", "iam"]):
                error_counts["permission"] = error_counts.get("permission", 0) + 1
            elif any(word in msg_lower for word in ["connection", "refused", "timeout", "network", "unreachable"]):
                error_counts["network"] = error_counts.get("network", 0) + 1
            elif any(word in msg_lower for word in ["database", "db", "sql", "connection pool"]):
                error_counts["database"] = error_counts.get("database", 0) + 1
            elif any(word in msg_lower for word in ["exception", "error", "failed", "traceback"]):
                error_counts["code_error"] = error_counts.get("code_error", 0) + 1
        
        # Find dominant error type
        dominant_error = None
        dominant_count = 0
        if error_counts:
            dominant_error = max(error_counts, key=error_counts.get)
            dominant_count = error_counts[dominant_error]
        
        # Decision logic - IMPROVED
        root_cause_type = RootCauseType.UNKNOWN
        description = "Unable to determine root cause"
        confidence = 0.3
        requires_infra_check = False
        
        # Check for dominant error pattern
        total_logs = len(state.log_evidence)
        
        if dominant_error and dominant_count > total_logs * 0.3:  # >30% of logs
            
            if dominant_error == "permission":
                root_cause_type = RootCauseType.PERMISSIONS
                description = (
                    f"Permission or authorization errors detected in {dominant_count}/{total_logs} logs. "
                    f"Common issues: IAM check failures, insufficient privileges."
                )
                confidence = min(0.9, 0.5 + (dominant_count / total_logs))
                requires_infra_check = True
                
            elif dominant_error == "network":
                root_cause_type = RootCauseType.NETWORK
                description = (
                    f"Network connectivity issues detected in {dominant_count}/{total_logs} logs. "
                    f"Common issues: connection refused, timeouts, DNS failures."
                )
                confidence = min(0.85, 0.5 + (dominant_count / total_logs))
                requires_infra_check = True
                
            elif dominant_error == "database":
                root_cause_type = RootCauseType.INFRASTRUCTURE
                description = (
                    f"Database connection issues detected in {dominant_count}/{total_logs} logs. "
                    f"Common issues: connection pool exhaustion, database unavailable."
                )
                confidence = min(0.8, 0.5 + (dominant_count / total_logs))
                requires_infra_check = True
                
            elif dominant_error == "code_error":
                root_cause_type = RootCauseType.CODE_ERROR
                description = (
                    f"Application code errors detected in {dominant_count}/{total_logs} logs. "
                    f"Common patterns: {', '.join(list(error_patterns.keys())[:3])}"
                )
                confidence = min(0.75, 0.4 + (dominant_count / total_logs))
        
        # Check for resource exhaustion (if metrics available)
        elif high_cpu or any(word in log_messages_lower for word in 
                            ["out of memory", "oom", "resource limit"]):
            root_cause_type = RootCauseType.RESOURCE_EXHAUSTION
            description = "Resource exhaustion detected (CPU/Memory)"
            confidence = 0.8
        
        # If no clear pattern, provide general summary
        elif error_counts:
            error_summary = ", ".join([f"{k}: {v}" for k, v in error_counts.items()])
            description = (
                f"Multiple issue types detected in {total_logs} logs: {error_summary}. "
                f"No single dominant root cause identified."
            )
            confidence = 0.4
        
        return RootCauseAnalysis(
            root_cause_type=root_cause_type,
            description=description,
            confidence=confidence,
            related_metrics=[m.metric_type for m in state.metrics[:3]] if state.metrics else [],
            related_logs=[log.message[:100] for log in state.log_evidence[:5]],
            requires_infra_check=requires_infra_check
        )
    
    def _analyze_with_llm(
        self,
        state: InvestigationState
    ) -> RootCauseAnalysis:
        """
        LLM-based analysis using Gemini
        
        Requires GOOGLE_API_KEY environment variable
        """
        # Prepare context for LLM
        context = self._prepare_llm_context(state)
        
        prompt = f"""You are an expert SRE analyzing a production incident.

Context:
{context}

Analyze the metrics and logs to determine:
1. Root cause type (code_error, infrastructure, network, permissions, resource_exhaustion)
2. Detailed description of what went wrong
3. Confidence level (0.0 to 1.0)
4. Whether infrastructure team should investigate (true/false)

Respond in JSON format:
{{
    "root_cause_type": "code_error|infrastructure|network|permissions|resource_exhaustion|unknown",
    "description": "Clear explanation of the root cause",
    "confidence": 0.85,
    "requires_infra_check": false
}}
"""
        
        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            
            return RootCauseAnalysis(
                root_cause_type=RootCauseType(result["root_cause_type"]),
                description=result["description"],
                confidence=result["confidence"],
                related_metrics=[m.metric_type for m in state.metrics[:3]] if state.metrics else [],
                related_logs=[log.message[:100] for log in state.log_evidence[:5]],
                requires_infra_check=result.get("requires_infra_check", False)
            )
            
        except Exception as e:
            self.logger.error(f"LLM analysis failed: {e}, falling back to rules")
            return self._analyze_with_rules(state)
    
    def _prepare_llm_context(
        self,
        state: InvestigationState
    ) -> str:
        """Prepare context for LLM"""
        context_parts = [
            f"Service: {state.service_name}",
            f"Time Window: {state.time_window.start} to {state.time_window.end}",
        ]
        
        if state.metrics:
            context_parts.append(f"\nMetrics ({len(state.metrics)} total):")
            for metric in state.metrics[:5]:
                context_parts.append(
                    f"  - {metric.metric_type}: {metric.value:.2f} "
                    f"(anomalous: {metric.is_anomalous})"
                )
        else:
            context_parts.append("\nMetrics: Not available yet")
        
        context_parts.append(f"\nLog Evidence ({len(state.log_evidence)} total):")
        
        for log in state.log_evidence[:15]:
            context_parts.append(
                f"  [{log.severity}] {log.message[:200]}"
            )
        
        return "\n".join(context_parts)


if __name__ == "__main__":
    import os
    from ..core import StateManager
    from ..agents.metric_scout import MetricScout
    from ..agents.log_collector import LogCollector
    from ..mcp import GCPMonitoringServer, GCPLoggingServer
    
    logging.basicConfig(level=logging.INFO)
    
    project_id = os.environ.get("GCP_PROJECT_ID", "demo-project")
    
    # Setup all agents
    monitoring = GCPMonitoringServer(project_id)
    logging_server = GCPLoggingServer(project_id)
    
    scout = MetricScout(monitoring)
    collector = LogCollector(logging_server)
    analyst = Analyst(use_llm=False)
    
    # Create and run full 3-step workflow
    state = StateManager.create_initial_state(
        intent="app_crash",
        service_name="demo-app"
    )
    
    print("\n" + "="*60)
    print("Running 3-Step Investigation Workflow")
    print("="*60)
    
    # Step 1: Find time window
    print("\n1. Metric Scout - Finding time window...")
    state = scout.investigate(state)
    print(f"   ✅ Time window: {state.time_window.start}")
    
    # Step 2: Collect logs
    print("\n2. Log Collector - Fetching logs...")
    state = collector.investigate(state)
    print(f"   ✅ Logs collected: {len(state.log_evidence)}")
    
    # Step 3: Analyze
    print("\n3. Analyst - Determining root cause...")
    state = analyst.investigate(state)
    
    if state.root_cause_analysis:
        print(f"   ✅ Root cause: {state.root_cause_analysis.root_cause_type.value}")
        print(f"   ✅ Confidence: {state.root_cause_analysis.confidence:.0%}")
        print(f"   ✅ Description: {state.root_cause_analysis.description}")
    
    print("\n" + "="*60)
    print("Investigation Complete!")
    print("="*60)
