"""
Analyst Agent - ENHANCED with LLM

Now with improved LLM reasoning for root cause analysis.
"""

import logging
from typing import Optional
import json
import os
from ..config import Config


from ..core.state import InvestigationState, RootCauseAnalysis, RootCauseType
from ..core.utils import extract_error_patterns


class Analyst:
    """
    Agent that performs root cause analysis.
    
    Can use either:
    - Rule-based analysis (fast, deterministic)
    - LLM-based analysis (smart, adaptive)
    """
    
    def __init__(self, use_llm: bool = False):
        """
        Initialize Analyst
        
        Args:
            use_llm: Whether to use actual LLM (requires GOOGLE_API_KEY)
        """
        self.use_llm = use_llm
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model = None
        
        if use_llm:
            try:
                import google.generativeai as genai

                api_key = Config.get_google_api_key()
                model_name = Config.get_model_name()
                if not api_key:
                    self.logger.error("GOOGLE_API_KEY not found in environment")
                    self.logger.warning("Falling back to rule-based analysis")
                    self.use_llm = False
                else:
                    genai.configure(api_key=api_key)
                    self.model = genai.GenerativeModel(
                        model_name,
                        generation_config={
                            "temperature": 0.3,  # Low temperature for consistent results
                            "top_p": 0.95,
                            "top_k": 40,
                            "max_output_tokens": 1024,
                        }
                    )
                    self.logger.info("✅ Using Gemini LLM for analysis")
                    
            except ImportError:
                self.logger.error("google-generativeai not installed")
                self.logger.warning("Run: pip install google-generativeai")
                self.use_llm = False
            except Exception as e:
                self.logger.error(f"Failed to initialize LLM: {e}")
                self.use_llm = False
        
        if not self.use_llm:
            self.logger.info("Using rule-based analysis")
    
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
        
        # Require logs for analysis
        if not state.log_evidence or len(state.log_evidence) == 0:
            error_msg = "No logs available for analysis"
            self.logger.warning(error_msg)
            state.add_error(error_msg)
            return state
        
        try:
            if self.use_llm and self.model:
                self.logger.info("🤖 Using AI reasoning for analysis...")
                analysis = self._analyze_with_llm(state)
            else:
                self.logger.info("📊 Using rule-based analysis...")
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
            
            # Fallback to rules if LLM fails
            if self.use_llm:
                self.logger.warning("LLM analysis failed, falling back to rules")
                analysis = self._analyze_with_rules(state)
                state.root_cause_analysis = analysis
        
        return state
    
    def _analyze_with_llm(
        self,
        state: InvestigationState
    ) -> RootCauseAnalysis:
        """
        LLM-based analysis using Gemini
        
        This is where the AI magic happens!
        """
        # Prepare context for LLM
        context = self._prepare_llm_context(state)
        
        prompt = f"""You are an expert Site Reliability Engineer (SRE) analyzing a production incident.

CONTEXT:
{context}

TASK:
Analyze the evidence and determine:
1. Root cause category (choose one):
   - code_error: Application code bugs, exceptions, crashes
   - infrastructure: Database, external service, resource issues
   - network: Connectivity, DNS, timeout issues
   - permissions: IAM, authorization, access denied issues  
   - resource_exhaustion: CPU/memory limits, OOM errors
   - unknown: Insufficient evidence to determine

2. Detailed description: Clear explanation of what went wrong

3. Confidence level: 0.0 to 1.0 based on evidence quality

4. Infrastructure check needed: true/false - should we investigate IAM/network/firewall?

IMPORTANT:
- Be specific in your description
- Base confidence on evidence quality
- If logs show clear patterns (>40% same error), confidence should be high
- If evidence is mixed or unclear, confidence should be lower

RESPOND in valid JSON format:
{{
    "root_cause_type": "permissions",
    "description": "Permission denied errors detected in 48 out of 50 logs. IAM role configuration appears incorrect for accessing Cloud Storage.",
    "confidence": 0.92,
    "requires_infra_check": true
}}
"""
        
        try:
            # Call Gemini
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up markdown code blocks if present
            response_text = response_text.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON response
            result = json.loads(response_text)
            
            self.logger.info(f"🤖 LLM Analysis: {result['root_cause_type']} ({result['confidence']:.0%})")
            
            return RootCauseAnalysis(
                root_cause_type=RootCauseType(result["root_cause_type"]),
                description=result["description"],
                confidence=float(result["confidence"]),
                related_metrics=[m.metric_type for m in state.metrics[:3]] if state.metrics else [],
                related_logs=[log.message[:100] for log in state.log_evidence[:5]],
                requires_infra_check=bool(result.get("requires_infra_check", False))
            )
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            self.logger.error(f"Response was: {response_text[:500]}")
            raise
        except Exception as e:
            self.logger.error(f"LLM analysis failed: {e}")
            raise
    
    def _analyze_with_rules(
        self,
        state: InvestigationState
    ) -> RootCauseAnalysis:
        """
        Rule-based analysis (fallback or default)
        """
        # Extract error patterns
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
        
        # Decision logic
        root_cause_type = RootCauseType.UNKNOWN
        description = "Unable to determine root cause"
        confidence = 0.3
        requires_infra_check = False
        
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
        
        elif high_cpu or any(word in log_messages_lower for word in 
                            ["out of memory", "oom", "resource limit"]):
            root_cause_type = RootCauseType.RESOURCE_EXHAUSTION
            description = "Resource exhaustion detected (CPU/Memory)"
            confidence = 0.8
        
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
    
    def _prepare_llm_context(
        self,
        state: InvestigationState
    ) -> str:
        """Prepare concise context for LLM"""
        context_parts = [
            f"Service: {state.service_name}",
            f"Time Window: {state.time_window.start} to {state.time_window.end}",
        ]
        
        if state.metrics:
            context_parts.append(f"\nMetrics ({len(state.metrics)} data points):")
            for metric in state.metrics[:5]:
                context_parts.append(
                    f"  - {metric.metric_type}: {metric.value:.2f} "
                    f"{'⚠️ ANOMALY' if metric.is_anomalous else ''}"
                )
        else:
            context_parts.append("\nMetrics: Not yet available")
        
        context_parts.append(f"\nLogs ({len(state.log_evidence)} entries):")
        
        # Sample logs intelligently - get diverse examples
        sample_size = min(15, len(state.log_evidence))
        step = len(state.log_evidence) // sample_size if sample_size > 0 else 1
        
        for i in range(0, len(state.log_evidence), step):
            if len([x for x in context_parts if x.startswith("  [")]) >= sample_size:
                break
            log = state.log_evidence[i]
            context_parts.append(
                f"  [{log.severity}] {log.message[:150]}"
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
    
    # Test both modes
    print("\n" + "="*70)
    print("Testing Analyst Agent - Both Modes")
    print("="*70)
    
    # Setup
    monitoring = GCPMonitoringServer(project_id)
    logging_server = GCPLoggingServer(project_id)
    
    scout = MetricScout(monitoring)
    collector = LogCollector(logging_server)
    
    # Create state
    state = StateManager.create_initial_state(
        intent="app_crash",
        service_name="aiops-demo-service"
    )
    
    # Gather evidence
    state = scout.investigate(state)
    state = collector.investigate(state)
    
    print(f"\n📊 Evidence collected:")
    print(f"   Logs: {len(state.log_evidence)}")
    print(f"   Metrics: {len(state.metrics)}")
    
    # Test 1: Rule-based
    print("\n" + "-"*70)
    print("TEST 1: Rule-Based Analysis")
    print("-"*70)
    
    analyst_rules = Analyst(use_llm=False)
    state1 = analyst_rules.investigate(state)
    
    if state1.root_cause_analysis:
        print(f"Root Cause: {state1.root_cause_analysis.root_cause_type.value}")
        print(f"Confidence: {state1.root_cause_analysis.confidence:.0%}")
        print(f"Description: {state1.root_cause_analysis.description}")
    
    # Test 2: LLM-based (if API key available)
    if os.environ.get("GOOGLE_API_KEY"):
        print("\n" + "-"*70)
        print("TEST 2: AI-Powered Analysis")
        print("-"*70)
        
        analyst_llm = Analyst(use_llm=True)
        state2 = analyst_llm.investigate(state)
        
        if state2.root_cause_analysis:
            print(f"Root Cause: {state2.root_cause_analysis.root_cause_type.value}")
            print(f"Confidence: {state2.root_cause_analysis.confidence:.0%}")
            print(f"Description: {state2.root_cause_analysis.description}")
    else:
        print("\n⚠️  Set GOOGLE_API_KEY to test LLM mode")
    
    print("\n" + "="*70)
