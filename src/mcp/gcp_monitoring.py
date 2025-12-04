"""
GCP Monitoring MCP Server

Provides deterministic access to Cloud Monitoring metrics with
hallucination prevention and automatic project ID injection.
"""
import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from google.cloud import monitoring_v3
from google.cloud.monitoring_v3 import query

from .mcp_base import BaseMCPServer, MCPToolDefinition, ValidationError


class GCPMonitoringServer(BaseMCPServer):
    """
    MCP Server for Google Cloud Monitoring
    
    Provides tools for:
    - Querying time series data
    - Detecting anomalies
    - Retrieving metric metadata
    """
    
    def __init__(
        self,
        project_id: str,
        credentials_path: Optional[str] = None
    ):
        """
        Initialize Monitoring MCP Server
        
        Args:
            project_id: GCP project ID
            credentials_path: Path to service account key
        """
        scopes = ["https://www.googleapis.com/auth/monitoring.read"]
        super().__init__(project_id, credentials_path, scopes)
        
        # Initialize monitoring client
        self.client = monitoring_v3.MetricServiceClient(credentials=self.credentials)
        self.project_name = f"projects/{self.project_id}"
        
        self.logger.info("GCP Monitoring MCP Server initialized")
    
    def test_connection(self) -> bool:
        """Test connection to Cloud Monitoring"""
        try:
            # Try to list metric descriptors (limited)
            request = monitoring_v3.ListMetricDescriptorsRequest(
                name=self.project_name,
                page_size=1
            )
            list(self.client.list_metric_descriptors(request=request))
            self.logger.info("Connection test successful")
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available monitoring tools"""
        return [
            MCPToolDefinition.define_tool(
                name="query_time_series",
                description="Query metric time series data for a specific resource and time range",
                parameters={
                    "metric_type": {
                        "type": "string",
                        "description": "Full metric type (e.g., 'run.googleapis.com/container/cpu/utilization')"
                    },
                    "resource_type": {
                        "type": "string",
                        "description": "Resource type (e.g., 'cloud_run_revision')"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time (ISO 8601 format)"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time (ISO 8601 format)"
                    },
                    "service_name": {
                        "type": "string",
                        "description": "Service name to filter (optional)"
                    },
                    "aggregation": {
                        "type": "string",
                        "description": "Aggregation method (ALIGN_MEAN, ALIGN_MAX, ALIGN_MIN)",
                        "default": "ALIGN_MEAN"
                    }
                },
                required=["metric_type", "resource_type", "start_time", "end_time"]
            ),
            MCPToolDefinition.define_tool(
                name="detect_anomalies",
                description="Detect anomalies in metric time series",
                parameters={
                    "metric_type": {
                        "type": "string",
                        "description": "Full metric type"
                    },
                    "resource_type": {
                        "type": "string",
                        "description": "Resource type"
                    },
                    "lookback_hours": {
                        "type": "integer",
                        "description": "Hours to look back for baseline",
                        "default": 24
                    },
                    "service_name": {
                        "type": "string",
                        "description": "Service name to filter (optional)"
                    }
                },
                required=["metric_type", "resource_type"]
            )
        ]
    
    def query_time_series(
        self,
        metric_type: str,
        resource_type: str,
        start_time: str,
        end_time: str,
        service_name: Optional[str] = None,
        aggregation: str = "ALIGN_MEAN",
        alignment_period_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Query time series data for a metric
        
        Args:
            metric_type: Full metric type path
            resource_type: GCP resource type
            start_time: ISO 8601 timestamp
            end_time: ISO 8601 timestamp
            service_name: Optional service name filter
            aggregation: Aggregation method
            alignment_period_seconds: Alignment period in seconds
        
        Returns:
            Dict with time series data
        """
        try:
            # Validate inputs
            self._validate_project_id()
            self._validate_time_range(start_time, end_time)
            self._check_rate_limit()
            
            # Convert timestamps
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # Build filter
            filter_parts = [
                f'resource.type = "{resource_type}"',
                f'metric.type = "{metric_type}"'
            ]
            
            if service_name:
                filter_parts.append(f'resource.labels.service_name = "{service_name}"')
            
            filter_str = " AND ".join(filter_parts)
            
            # Build time interval
            interval = monitoring_v3.TimeInterval(
                {
                    "end_time": {"seconds": int(end_dt.timestamp())},
                    "start_time": {"seconds": int(start_dt.timestamp())},
                }
            )
            
            # Build aggregation
            aggregation_obj = monitoring_v3.Aggregation(
                {
                    "alignment_period": {"seconds": alignment_period_seconds},
                    "per_series_aligner": getattr(
                        monitoring_v3.Aggregation.Aligner,
                        aggregation
                    ),
                }
            )
            
            # Query
            request = monitoring_v3.ListTimeSeriesRequest(
                name=self.project_name,
                filter=filter_str,
                interval=interval,
                aggregation=aggregation_obj,
                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL
            )
            
            results = self.client.list_time_series(request=request)
            
            # Parse results
            time_series_data = []
            for ts in results:
                points = []
                for point in ts.points:
                    # Extract value based on type
                    value = None
                    if point.value.double_value:
                        value = point.value.double_value
                    elif point.value.int64_value:
                        value = float(point.value.int64_value)
                    
                    points.append({
                        "timestamp": point.interval.end_time.isoformat(),
                        "value": value
                    })
                
                # Extract resource labels
                resource_labels = dict(ts.resource.labels)
                
                time_series_data.append({
                    "metric": dict(ts.metric.labels),
                    "resource": resource_labels,
                    "points": points
                })
            
            self.logger.info(
                f"Retrieved {len(time_series_data)} time series "
                f"for {metric_type}"
            )
            
            return {
                "success": True,
                "metric_type": metric_type,
                "resource_type": resource_type,
                "time_range": {
                    "start": start_time,
                    "end": end_time
                },
                "time_series_count": len(time_series_data),
                "time_series": self._sanitize_response(time_series_data, max_items=50)
            }
            
        except Exception as e:
            return self._handle_api_error(e, "Query time series")
    
    def detect_anomalies(
        self,
        metric_type: str,
        resource_type: str,
        lookback_hours: int = 24,
        service_name: Optional[str] = None,
        threshold_sigma: float = 2.0
    ) -> Dict[str, Any]:
        """
        Detect anomalies in recent metrics compared to historical baseline
        
        Args:
            metric_type: Full metric type path
            resource_type: GCP resource type
            lookback_hours: Hours to look back for baseline
            service_name: Optional service name filter
            threshold_sigma: Standard deviations for anomaly threshold
        
        Returns:
            Dict with anomaly detection results
        """
        try:
            self._validate_project_id()
            self._check_rate_limit()
            
            # Define time windows
            end_time = datetime.utcnow()
            baseline_start = end_time - timedelta(hours=lookback_hours)
            recent_start = end_time - timedelta(minutes=15)  # Last 15 minutes
            
            # Get baseline data
            baseline_data = self.query_time_series(
                metric_type=metric_type,
                resource_type=resource_type,
                start_time=baseline_start.isoformat() + 'Z',
                end_time=recent_start.isoformat() + 'Z',
                service_name=service_name
            )
            
            # Get recent data
            recent_data = self.query_time_series(
                metric_type=metric_type,
                resource_type=resource_type,
                start_time=recent_start.isoformat() + 'Z',
                end_time=end_time.isoformat() + 'Z',
                service_name=service_name
            )
            
            if not baseline_data["success"] or not recent_data["success"]:
                return {
                    "success": False,
                    "error": "Failed to retrieve metric data"
                }
            
            # Calculate statistics
            anomalies = []
            
            for ts_recent in recent_data.get("time_series", []):
                resource_id = ts_recent["resource"]
                recent_points = ts_recent["points"]
                
                if not recent_points:
                    continue
                
                # Find matching baseline
                baseline_points = []
                for ts_baseline in baseline_data.get("time_series", []):
                    if ts_baseline["resource"] == resource_id:
                        baseline_points = ts_baseline["points"]
                        break
                
                if not baseline_points:
                    continue
                
                # Calculate baseline stats
                baseline_values = [p["value"] for p in baseline_points if p["value"] is not None]
                
                if len(baseline_values) < 2:
                    continue
                
                import statistics
                mean = statistics.mean(baseline_values)
                std_dev = statistics.stdev(baseline_values)
                
                # Check recent points for anomalies
                for point in recent_points:
                    if point["value"] is None:
                        continue
                    
                    if std_dev > 0:
                        z_score = abs((point["value"] - mean) / std_dev)
                        is_anomalous = z_score > threshold_sigma
                        
                        if is_anomalous:
                            anomalies.append({
                                "timestamp": point["timestamp"],
                                "value": point["value"],
                                "baseline_mean": mean,
                                "baseline_std": std_dev,
                                "z_score": z_score,
                                "resource": resource_id
                            })
            
            self.logger.info(f"Detected {len(anomalies)} anomalies")
            
            return {
                "success": True,
                "metric_type": metric_type,
                "lookback_hours": lookback_hours,
                "anomaly_count": len(anomalies),
                "anomalies": anomalies,
                "threshold_sigma": threshold_sigma
            }
            
        except Exception as e:
            return self._handle_api_error(e, "Detect anomalies")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize server
    project_id = os.environ.get("GCP_PROJECT_ID", "demo-project")
    
    try:
        server = GCPMonitoringServer(project_id=project_id)
        
        print("✅ Server initialized")
        print(f"Available tools: {len(server.get_available_tools())}")
        
        # Test connection
        if server.test_connection():
            print("✅ Connection test passed")
        
        # Example: Query CPU metrics
        result = server.query_time_series(
            metric_type="run.googleapis.com/container/cpu/utilization",
            resource_type="cloud_run_revision",
            start_time=(datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z',
            end_time=datetime.utcnow().isoformat() + 'Z',
            service_name="demo-app"
        )
        
        print(f"\nQuery result: {result.get('time_series_count', 0)} time series found")
        
    except Exception as e:
        print(f"❌ Error: {e}")
