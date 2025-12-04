"""
Utility functions for AIOps Agent
"""

import os
import yaml
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from pathlib import Path
import json


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('aiops_agent.log')
        ]
    )
    return logging.getLogger('aiops_agent')


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load YAML configuration file
    
    Args:
        config_path: Path to YAML config file
    
    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Replace environment variables
    config = _replace_env_vars(config)
    
    return config


def _replace_env_vars(config: Any) -> Any:
    """
    Recursively replace ${VAR} patterns with environment variables
    
    Args:
        config: Configuration dict or value
    
    Returns:
        Configuration with replaced values
    """
    if isinstance(config, dict):
        return {k: _replace_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_replace_env_vars(item) for item in config]
    elif isinstance(config, str):
        # Replace ${VAR} or $VAR patterns
        if config.startswith('${') and config.endswith('}'):
            var_name = config[2:-1]
            return os.environ.get(var_name, config)
        return config
    else:
        return config


def parse_time_range(
    time_str: Optional[str] = None,
    duration_minutes: int = 60
) -> Dict[str, str]:
    """
    Parse time range for queries
    
    Args:
        time_str: ISO timestamp or relative time (e.g., "1h ago")
        duration_minutes: Duration of the time window
    
    Returns:
        Dict with 'start' and 'end' ISO timestamps
    """
    if time_str:
        # Parse relative time
        if 'ago' in time_str.lower():
            amount = int(''.join(filter(str.isdigit, time_str)))
            unit = ''.join(filter(str.isalpha, time_str.lower().replace('ago', ''))).strip()
            
            if unit in ['h', 'hour', 'hours']:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=amount)
            elif unit in ['m', 'min', 'minute', 'minutes']:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(minutes=amount)
            elif unit in ['d', 'day', 'days']:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=amount)
            else:
                # Default to hours
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=amount)
        else:
            # Parse ISO timestamp
            try:
                start_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                end_time = start_time + timedelta(minutes=duration_minutes)
            except ValueError:
                # Default to last hour
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=1)
    else:
        # Default: last hour
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
    
    return {
        "start": start_time.isoformat() + 'Z',
        "end": end_time.isoformat() + 'Z'
    }


def format_metric_filter(
    resource_type: str,
    metric_type: str,
    service_name: Optional[str] = None
) -> str:
    """
    Create a Cloud Monitoring metric filter
    
    Args:
        resource_type: GCP resource type (e.g., 'cloud_run_revision')
        metric_type: Metric type (e.g., 'cpu/utilization')
        service_name: Optional service name filter
    
    Returns:
        Formatted filter string
    """
    filter_parts = [
        f'resource.type="{resource_type}"',
        f'metric.type="{metric_type}"'
    ]
    
    if service_name:
        filter_parts.append(f'resource.labels.service_name="{service_name}"')
    
    return ' AND '.join(filter_parts)


def format_log_filter(
    resource_type: str,
    severity: Optional[str] = None,
    time_range: Optional[Dict[str, str]] = None,
    service_name: Optional[str] = None
) -> str:
    """
    Create a Cloud Logging filter
    
    Args:
        resource_type: GCP resource type
        severity: Log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        time_range: Time range with 'start' and 'end'
        service_name: Optional service name filter
    
    Returns:
        Formatted filter string
    """
    filter_parts = [f'resource.type="{resource_type}"']
    
    if severity:
        filter_parts.append(f'severity>="{severity}"')
    
    if service_name:
        filter_parts.append(f'resource.labels.service_name="{service_name}"')
    
    if time_range:
        filter_parts.append(f'timestamp>="{time_range["start"]}"')
        filter_parts.append(f'timestamp<="{time_range["end"]}"')
    
    return ' AND '.join(filter_parts)


def truncate_logs(logs: list, max_entries: int = 100) -> tuple:
    """
    Truncate log entries to prevent context overflow
    
    Args:
        logs: List of log entries
        max_entries: Maximum number of entries to keep
    
    Returns:
        Tuple of (truncated_logs, was_truncated)
    """
    if len(logs) <= max_entries:
        return logs, False
    
    # Keep first and last entries, sample from middle
    first_half = max_entries // 2
    second_half = max_entries - first_half
    
    truncated = logs[:first_half] + logs[-second_half:]
    
    return truncated, True


def calculate_anomaly_score(
    current_value: float,
    historical_mean: float,
    historical_std: float,
    threshold_sigma: float = 2.0
) -> tuple:
    """
    Calculate if a metric value is anomalous
    
    Args:
        current_value: Current metric value
        historical_mean: Historical mean
        historical_std: Historical standard deviation
        threshold_sigma: Number of standard deviations for anomaly
    
    Returns:
        Tuple of (is_anomalous, score)
    """
    if historical_std == 0:
        return False, 0.0
    
    z_score = abs((current_value - historical_mean) / historical_std)
    is_anomalous = z_score > threshold_sigma
    
    return is_anomalous, z_score


def sanitize_for_llm(text: str, max_length: int = 1000) -> str:
    """
    Sanitize and truncate text for LLM input
    
    Args:
        text: Input text
        max_length: Maximum character length
    
    Returns:
        Sanitized text
    """
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "... [truncated]"
    
    return text


def extract_error_patterns(log_entries: list) -> Dict[str, int]:
    """
    Extract common error patterns from log entries
    
    Args:
        log_entries: List of log entry dicts
    
    Returns:
        Dict mapping error patterns to occurrence counts
    """
    error_patterns = {}
    
    for entry in log_entries:
        message = entry.get('message', '')
        
        # Extract error type (simplified)
        if 'Exception' in message:
            error_type = message.split('Exception')[0].split()[-1] + 'Exception'
            error_patterns[error_type] = error_patterns.get(error_type, 0) + 1
        elif 'Error' in message:
            error_type = message.split('Error')[0].split()[-1] + 'Error'
            error_patterns[error_type] = error_patterns.get(error_type, 0) + 1
        elif 'error' in message.lower():
            error_patterns['GenericError'] = error_patterns.get('GenericError', 0) + 1
    
    # Sort by frequency
    sorted_patterns = dict(sorted(error_patterns.items(), key=lambda x: x[1], reverse=True))
    
    return sorted_patterns


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted string (e.g., "2m 30s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds:.0f}s"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    return f"{hours}h {remaining_minutes}m"


def get_project_root() -> Path:
    """Get the project root directory"""
    return Path(__file__).parent.parent.parent


def load_env_file(env_path: Optional[str] = None):
    """
    Load environment variables from .env file
    
    Args:
        env_path: Path to .env file (default: project root)
    """
    try:
        from dotenv import load_dotenv
        
        if env_path is None:
            env_path = get_project_root() / '.env'
        
        load_dotenv(env_path)
    except ImportError:
        logging.warning("python-dotenv not installed, skipping .env file loading")


# Example usage
if __name__ == "__main__":
    logger = setup_logging("DEBUG")
    logger.info("Utilities module loaded")
    
    # Test time range parsing
    time_range = parse_time_range("1h ago", 15)
    print(f"Time range: {time_range}")
    
    # Test metric filter
    metric_filter = format_metric_filter(
        "cloud_run_revision",
        "run.googleapis.com/container/cpu/utilization",
        "demo-app"
    )
    print(f"Metric filter: {metric_filter}")
    
    # Test log filter
    log_filter = format_log_filter(
        "cloud_run_revision",
        "ERROR",
        time_range,
        "demo-app"
    )
    print(f"Log filter: {log_filter}")
    
    # Test anomaly detection
    is_anomalous, score = calculate_anomaly_score(95.0, 50.0, 15.0, 2.0)
    print(f"Anomalous: {is_anomalous}, Score: {score:.2f}")
