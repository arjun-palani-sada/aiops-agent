"""
State Management for AIOps Agent

This module handles the state object that flows through the sequential workflow.
The state is passed between agents and accumulates information at each step.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from enum import Enum


class IntentType(str, Enum):
    """Types of intents the system can handle"""
    APP_CRASH = "app_crash"
    APP_ERROR = "app_error"
    PERFORMANCE_ISSUE = "performance_issue"
    CONNECTIVITY_ISSUE = "connectivity_issue"
    UNKNOWN = "unknown"


class RootCauseType(str, Enum):
    """Types of root causes"""
    CODE_ERROR = "code_error"
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"
    PERMISSIONS = "permissions"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNKNOWN = "unknown"


class TimeWindow(BaseModel):
    """Time window for investigation"""
    start: str = Field(..., description="ISO 8601 timestamp")
    end: str = Field(..., description="ISO 8601 timestamp")
    anomaly_detected: bool = Field(default=False)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class MetricData(BaseModel):
    """Metric information"""
    metric_type: str
    value: float
    timestamp: str
    is_anomalous: bool = False
    threshold: Optional[float] = None


class LogEntry(BaseModel):
    """Log entry information"""
    timestamp: str
    severity: str
    message: str
    resource: Optional[Dict[str, Any]] = None
    labels: Optional[Dict[str, str]] = None
    trace_id: Optional[str] = None


class RootCauseAnalysis(BaseModel):
    """Root cause analysis results"""
    root_cause_type: RootCauseType
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    related_metrics: List[str] = Field(default_factory=list)
    related_logs: List[str] = Field(default_factory=list)
    requires_infra_check: bool = False


class InfrastructureFindings(BaseModel):
    """Infrastructure detective findings"""
    permission_errors: List[str] = Field(default_factory=list)
    network_errors: List[str] = Field(default_factory=list)
    firewall_issues: List[str] = Field(default_factory=list)
    audit_log_entries: List[Dict[str, Any]] = Field(default_factory=list)


class InvestigationState(BaseModel):
    """
    The state object that flows through the sequential workflow.
    
    This accumulates information from each agent:
    1. Metric Scout adds time_window and metrics
    2. Log Collector adds log_evidence
    3. Analyst adds root_cause_analysis
    4. Infra Detective (conditional) adds infrastructure_findings
    """
    
    # Initial input
    intent: IntentType
    service_name: str
    initial_time_range: Optional[TimeWindow] = None
    user_query: str = ""
    
    # Step 2a: Metric Scout output
    time_window: Optional[TimeWindow] = None
    metrics: List[MetricData] = Field(default_factory=list)
    
    # Step 2b: Log Collector output
    log_evidence: List[LogEntry] = Field(default_factory=list)
    log_summary: Optional[str] = None
    
    # Step 2c: Analyst output
    root_cause_analysis: Optional[RootCauseAnalysis] = None
    
    # Step 2d: Infra Detective output (conditional)
    infrastructure_findings: Optional[InfrastructureFindings] = None
    
    # Metadata
    investigation_start: datetime = Field(default_factory=datetime.utcnow)
    investigation_end: Optional[datetime] = None
    agent_sequence: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_agent_step(self, agent_name: str) -> None:
        """Record which agent processed this state"""
        self.agent_sequence.append(f"{agent_name}:{datetime.utcnow().isoformat()}")
    
    def add_error(self, error: str) -> None:
        """Add an error message"""
        self.errors.append(f"{datetime.utcnow().isoformat()}: {error}")
    
    def complete_investigation(self) -> None:
        """Mark investigation as complete"""
        self.investigation_end = datetime.utcnow()
    
    def get_duration_seconds(self) -> Optional[float]:
        """Get investigation duration in seconds"""
        if self.investigation_end:
            delta = self.investigation_end - self.investigation_start
            return delta.total_seconds()
        return None
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Convert state to a clean dictionary for the summarizer.
        This removes unnecessary technical details.
        """
        return {
            "service": self.service_name,
            "issue_type": self.intent.value,
            "time_window": {
                "start": self.time_window.start if self.time_window else None,
                "end": self.time_window.end if self.time_window else None,
            } if self.time_window else None,
            "key_metrics": [
                {
                    "type": m.metric_type,
                    "value": m.value,
                    "anomalous": m.is_anomalous
                }
                for m in self.metrics[:5]  # Top 5 only
            ],
            "error_count": len([log for log in self.log_evidence if log.severity == "ERROR"]),
            "root_cause": {
                "type": self.root_cause_analysis.root_cause_type.value,
                "description": self.root_cause_analysis.description,
                "confidence": self.root_cause_analysis.confidence
            } if self.root_cause_analysis else None,
            "infrastructure_issues": {
                "permissions": self.infrastructure_findings.permission_errors,
                "network": self.infrastructure_findings.network_errors,
            } if self.infrastructure_findings else None,
            "duration_seconds": self.get_duration_seconds()
        }


class StateManager:
    """Helper class for managing state across the workflow"""
    
    @staticmethod
    def create_initial_state(
        intent: str,
        service_name: str,
        user_query: str = "",
        initial_time_range: Optional[Dict[str, str]] = None
    ) -> InvestigationState:
        """Create initial investigation state"""
        
        # Convert string intent to enum
        try:
            intent_enum = IntentType(intent.lower())
        except ValueError:
            intent_enum = IntentType.UNKNOWN
        
        # Create time window if provided
        time_window = None
        if initial_time_range:
            time_window = TimeWindow(**initial_time_range)
        
        return InvestigationState(
            intent=intent_enum,
            service_name=service_name,
            user_query=user_query,
            initial_time_range=time_window
        )
    
    @staticmethod
    def validate_state_transition(
        state: InvestigationState,
        from_agent: str,
        to_agent: str
    ) -> bool:
        """
        Validate that the state has required information for the next agent.
        This prevents agents from running without necessary prerequisites.
        """
        
        transitions = {
            "metric_scout": {
                "required": ["intent", "service_name"],
                "produces": ["time_window", "metrics"]
            },
            "log_collector": {
                "required": ["time_window"],
                "produces": ["log_evidence"]
            },
            "analyst": {
                "required": ["metrics", "log_evidence"],
                "produces": ["root_cause_analysis"]
            },
            "infra_detective": {
                "required": ["root_cause_analysis"],
                "produces": ["infrastructure_findings"]
            }
        }
        
        if to_agent not in transitions:
            return True  # Unknown agent, allow
        
        required_fields = transitions[to_agent]["required"]
        
        for field in required_fields:
            value = getattr(state, field, None)
            if value is None or (isinstance(value, list) and len(value) == 0):
                return False
        
        return True
    
    @staticmethod
    def get_context_size_estimate(state: InvestigationState) -> int:
        """Estimate the token count of the current state (rough approximation)"""
        state_json = state.model_dump_json()
        # Rough estimate: 1 token ≈ 4 characters
        return len(state_json) // 4


# Example usage and testing
if __name__ == "__main__":
    # Create initial state
    state = StateManager.create_initial_state(
        intent="app_crash",
        service_name="demo-app",
        user_query="Why is my app crashing?",
        initial_time_range={
            "start": "2025-12-04T10:00:00Z",
            "end": "2025-12-04T11:00:00Z"
        }
    )
    
    print("Initial State:")
    print(state.model_dump_json(indent=2))
    
    # Simulate Metric Scout processing
    state.add_agent_step("metric_scout")
    state.time_window = TimeWindow(
        start="2025-12-04T10:15:00Z",
        end="2025-12-04T10:20:00Z",
        anomaly_detected=True,
        confidence=0.85
    )
    state.metrics.append(MetricData(
        metric_type="cpu_utilization",
        value=95.0,
        timestamp="2025-12-04T10:17:30Z",
        is_anomalous=True,
        threshold=80.0
    ))
    
    print("\nAfter Metric Scout:")
    print(f"Time Window: {state.time_window.start} to {state.time_window.end}")
    print(f"Metrics collected: {len(state.metrics)}")
    
    # Validate transition
    can_proceed = StateManager.validate_state_transition(
        state, "metric_scout", "log_collector"
    )
    print(f"\nCan proceed to log_collector: {can_proceed}")
    
    print(f"\nEstimated context size: {StateManager.get_context_size_estimate(state)} tokens")
