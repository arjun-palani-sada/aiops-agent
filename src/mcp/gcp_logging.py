"""
GCP Logging MCP Server - IMPROVED VERSION

Provides deterministic access to Cloud Logging.
IMPROVED: Better message extraction from different log types
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from google.cloud import logging_v2

from src.mcp.mcp_base import BaseMCPServer, MCPToolDefinition, ValidationError


class GCPLoggingServer(BaseMCPServer):
    """MCP Server for Google Cloud Logging"""
    
    def __init__(
        self,
        project_id: str,
        credentials_path: Optional[str] = None
    ):
        scopes = ["https://www.googleapis.com/auth/logging.read"]
        super().__init__(project_id, credentials_path, scopes)
        
        self.client = logging_v2.Client(
            project=self.project_id,
            credentials=self.credentials
        )
        
        self.logger.info("GCP Logging MCP Server initialized")
    
    def test_connection(self) -> bool:
        """Test connection to Cloud Logging"""
        try:
            entries = list(self.client.list_entries(max_results=1))
            self.logger.info("Connection test successful")
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available logging tools"""
        return [
            MCPToolDefinition.define_tool(
                name="list_entries",
                description="List application log entries with filters",
                parameters={
                    "filter": {
                        "type": "string",
                        "description": "Cloud Logging filter string"
                    },
                    "max_entries": {
                        "type": "integer",
                        "description": "Maximum entries to return",
                        "default": 100
                    },
                    "order_by": {
                        "type": "string",
                        "description": "Sort order (timestamp desc/asc)",
                        "default": "timestamp desc"
                    }
                },
                required=["filter"]
            ),
            MCPToolDefinition.define_tool(
                name="list_audit_logs",
                description="List audit log entries for security analysis",
                parameters={
                    "resource_type": {
                        "type": "string",
                        "description": "GCP resource type"
                    },
                    "time_range": {
                        "type": "object",
                        "description": "Time range with start and end"
                    },
                    "max_entries": {
                        "type": "integer",
                        "default": 100
                    }
                },
                required=["resource_type"]
            )
        ]
    
    def list_entries(
        self,
        filter_str: str,
        max_entries: int = 100,
        order_by: str = "timestamp desc"
    ) -> Dict[str, Any]:
        """
        List log entries with filter
        
        Args:
            filter_str: Cloud Logging filter
            max_entries: Maximum entries to return
            order_by: Sort order
            
        Returns:
            Dict with log entries
        """
        try:
            self._check_rate_limit()
            
            entries = list(self.client.list_entries(
                filter_=filter_str,
                order_by=order_by,
                max_results=max_entries
            ))
            
            logs = []
            for entry in entries:
                log_dict = {
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    "severity": str(entry.severity) if entry.severity else "UNKNOWN",
                    "log_name": entry.log_name,
                }

                # IMPROVED: Extract message from multiple possible fields
                message = self._extract_message_from_entry(entry)
                log_dict["message"] = message

                # Add resource info
                if entry.resource:
                    log_dict["resource"] = {
                        "type": entry.resource.type,
                        "labels": dict(entry.resource.labels) if entry.resource.labels else {}
                    }

                # Add labels
                if entry.labels:
                    log_dict["labels"] = dict(entry.labels)

                logs.append(log_dict)

            self.logger.info(f"Retrieved {len(logs)} log entries")

            return {
                "success": True,
                "count": len(logs),
                "logs": self._sanitize_response(logs, max_items=max_entries)
            }

        except Exception as e:
            return self._handle_api_error(e, "List log entries")

    def _extract_message_from_entry(self, entry) -> str:
        """
        IMPROVED: Extract message from log entry

        Cloud Run logs can have different payload types:
        - text_payload: Simple string
        - json_payload: Structured data
        - proto_payload: Protocol buffer (audit logs)
        - http_request: HTTP request metadata

        Args:
            entry: Cloud Logging entry object

        Returns:
            Extracted message string
        """
        # Try text payload first (most common for app logs)
        if hasattr(entry, 'text_payload') and entry.text_payload:
            return str(entry.text_payload)

        # Try JSON payload
        if hasattr(entry, 'json_payload') and entry.json_payload:
            payload = entry.json_payload

            # Common fields in json_payload
            if isinstance(payload, dict):
                # Try 'message' field
                if 'message' in payload:
                    return str(payload['message'])

                # Try 'msg' field
                if 'msg' in payload:
                    return str(payload['msg'])

                # Try 'error' field
                if 'error' in payload:
                    return f"Error: {payload['error']}"

                # Convert entire payload to string as fallback
                import json
                return json.dumps(payload)

            return str(payload)

        # Try proto payload (audit logs)
        if hasattr(entry, 'proto_payload') and entry.proto_payload:
            # Extract meaningful info from proto payload
            try:
                payload = entry.proto_payload
                if hasattr(payload, 'status'):
                    return f"Audit log: {payload.status.message if hasattr(payload.status, 'message') else 'Status event'}"
                return "Audit log entry"
            except:
                pass

        # Try HTTP request info (access logs)
        if hasattr(entry, 'http_request') and entry.http_request:
            http = entry.http_request

            # http_request can be either a dict or an object
            if isinstance(http, dict):
                status = http.get('status', 'unknown')
                method = http.get('requestMethod', 'unknown')
            else:
                status = getattr(http, 'status', 'unknown')
                method = getattr(http, 'request_method', 'unknown')

            # Create meaningful message from HTTP info
            message_parts = [f"HTTP {method} request"]

            if status and status != 'unknown':
                message_parts.append(f"returned status {status}")

                # Add context based on status code
                try:
                    status_int = int(status)
                    if status_int >= 500:
                        message_parts.append("(Server Error)")
                    elif status_int >= 400:
                        if status_int == 403:
                            message_parts.append("(Permission Denied)")
                        elif status_int == 404:
                            message_parts.append("(Not Found)")
                        else:
                            message_parts.append("(Client Error)")
                except (ValueError, TypeError):
                    pass

            return " ".join(message_parts)

        # Fallback: Use entry as string
        return f"Log entry with severity {str(entry.severity) if entry.severity else 'UNKNOWN'}"

    def list_audit_logs(
        self,
        resource_type: str,
        time_range: Optional[Dict[str, str]] = None,
        max_entries: int = 100
    ) -> Dict[str, Any]:
        """
        List audit log entries

        Args:
            resource_type: GCP resource type
            time_range: Optional time range filter
            max_entries: Maximum entries to return

        Returns:
            Dict with audit log entries
        """
        try:
            self._check_rate_limit()

            filter_parts = [
                f'resource.type="{resource_type}"',
                'protoPayload.@type="type.googleapis.com/google.cloud.audit.AuditLog"'
            ]

            if time_range:
                if "start" in time_range:
                    filter_parts.append(f'timestamp>="{time_range["start"]}"')
                if "end" in time_range:
                    filter_parts.append(f'timestamp<="{time_range["end"]}"')

            filter_str = " AND ".join(filter_parts)

            return self.list_entries(
                filter_str=filter_str,
                max_entries=max_entries,
                order_by="timestamp desc"
            )

        except Exception as e:
            return self._handle_api_error(e, "List audit logs")


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)

    project_id = os.environ.get("GCP_PROJECT_ID", "demo-project")

    try:
        server = GCPLoggingServer(project_id=project_id)

        print("✅ Server initialized")
        print(f"Available tools: {len(server.get_available_tools())}")

        if server.test_connection():
            print("✅ Connection test passed")

        result = server.list_entries(
            filter_str='severity >= "ERROR"',
            max_entries=10
        )

        print(f"\nQuery result: {result.get('count', 0)} logs found")

        # Show first few messages
        if result.get('logs'):
            print("\nFirst 3 log messages:")
            for i, log in enumerate(result['logs'][:3], 1):
                print(f"\n{i}. [{log.get('severity')}] {log.get('message', '')[:150]}")

    except Exception as e:
        print(f"❌ Error: {e}")