"""
Base MCP (Model Context Protocol) Server

This module provides the foundation for GCP service integration with
deterministic, secure, and rate-limited API access.
"""

import os
import logging
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from google.oauth2 import service_account
from google.auth import default
import google.auth.transport.requests


class MCPError(Exception):
    """Base exception for MCP errors"""
    pass


class AuthenticationError(MCPError):
    """Authentication failed"""
    pass


class RateLimitError(MCPError):
    """Rate limit exceeded"""
    pass


class ValidationError(MCPError):
    """Input validation failed"""
    pass


class BaseMCPServer(ABC):
    """
    Base class for all MCP servers
    
    Provides:
    - Authentication handling
    - Error management
    - Input validation
    - Logging
    - Rate limiting (basic)
    """
    
    def __init__(
        self,
        project_id: str,
        credentials_path: Optional[str] = None,
        scopes: Optional[List[str]] = None
    ):
        """
        Initialize MCP server
        
        Args:
            project_id: GCP project ID
            credentials_path: Path to service account key (optional)
            scopes: OAuth scopes required
        """
        self.project_id = project_id
        self.logger = logging.getLogger(self.__class__.__name__)
        self.scopes = scopes or []
        
        # Initialize credentials
        self.credentials = self._initialize_credentials(credentials_path)
        
        # Track API calls for rate limiting
        self.api_call_count = 0
        self.max_calls_per_minute = 60
        
        self.logger.info(f"Initialized {self.__class__.__name__} for project {project_id}")
    
    def _initialize_credentials(
        self,
        credentials_path: Optional[str] = None
    ):
        """
        Initialize Google Cloud credentials
        
        Args:
            credentials_path: Path to service account key file
        
        Returns:
            Credentials object
        
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            if credentials_path and os.path.exists(credentials_path):
                # Use service account
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=self.scopes
                )
                self.logger.info("Using service account credentials")
            else:
                # Use application default credentials
                credentials, project = default(scopes=self.scopes)
                if not self.project_id:
                    self.project_id = project
                self.logger.info("Using application default credentials")
            
            return credentials
            
        except Exception as e:
            raise AuthenticationError(f"Failed to initialize credentials: {str(e)}")
    
    def _refresh_credentials(self):
        """Refresh credentials if needed"""
        try:
            if not self.credentials.valid:
                request = google.auth.transport.requests.Request()
                self.credentials.refresh(request)
                self.logger.debug("Credentials refreshed")
        except Exception as e:
            raise AuthenticationError(f"Failed to refresh credentials: {str(e)}")
    
    def _check_rate_limit(self):
        """
        Basic rate limiting check
        
        Raises:
            RateLimitError: If rate limit exceeded
        """
        self.api_call_count += 1
        
        if self.api_call_count > self.max_calls_per_minute:
            raise RateLimitError(
                f"Rate limit exceeded: {self.max_calls_per_minute} calls/minute"
            )
    
    def _validate_project_id(self):
        """Validate project ID is set"""
        if not self.project_id:
            raise ValidationError("Project ID is required")
    
    def _validate_time_range(self, start: str, end: str):
        """
        Validate time range format
        
        Args:
            start: Start timestamp (ISO 8601)
            end: End timestamp (ISO 8601)
        
        Raises:
            ValidationError: If format is invalid
        """
        from datetime import datetime
        
        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            
            if start_dt >= end_dt:
                raise ValidationError("Start time must be before end time")
            
            # Check if time range is reasonable (not too large)
            duration = (end_dt - start_dt).total_seconds()
            max_duration = 24 * 3600  # 24 hours
            
            if duration > max_duration:
                raise ValidationError(
                    f"Time range too large: {duration/3600:.1f}h (max: 24h)"
                )
                
        except ValueError as e:
            raise ValidationError(f"Invalid timestamp format: {str(e)}")
    
    def _handle_api_error(self, error: Exception, operation: str) -> Dict[str, Any]:
        """
        Handle API errors consistently
        
        Args:
            error: The exception that occurred
            operation: Description of the operation
        
        Returns:
            Error response dict
        """
        error_msg = f"{operation} failed: {str(error)}"
        self.logger.error(error_msg)
        
        return {
            "success": False,
            "error": error_msg,
            "error_type": type(error).__name__
        }
    
    def _sanitize_response(
        self,
        data: Any,
        max_items: Optional[int] = None
    ) -> Any:
        """
        Sanitize response data to prevent context overflow
        
        Args:
            data: Response data
            max_items: Maximum number of items to return
        
        Returns:
            Sanitized data
        """
        if isinstance(data, list) and max_items and len(data) > max_items:
            self.logger.warning(
                f"Truncating response: {len(data)} items -> {max_items} items"
            )
            return data[:max_items]
        
        return data
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test connection to the service
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available tools this server provides
        
        Returns:
            List of tool definitions
        """
        pass
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get information about this MCP server
        
        Returns:
            Server metadata
        """
        return {
            "name": self.__class__.__name__,
            "project_id": self.project_id,
            "tools": self.get_available_tools(),
            "scopes": self.scopes,
            "api_calls": self.api_call_count
        }


class MCPToolDefinition:
    """Helper class for defining MCP tools"""
    
    @staticmethod
    def define_tool(
        name: str,
        description: str,
        parameters: Dict[str, Any],
        required: List[str]
    ) -> Dict[str, Any]:
        """
        Define an MCP tool
        
        Args:
            name: Tool name
            description: Tool description
            parameters: Parameter definitions
            required: Required parameter names
        
        Returns:
            Tool definition dict
        """
        return {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required
            }
        }


# Example usage
if __name__ == "__main__":
    # Test base functionality
    logging.basicConfig(level=logging.INFO)
    
    class TestMCPServer(BaseMCPServer):
        """Test implementation"""
        
        def test_connection(self) -> bool:
            return True
        
        def get_available_tools(self) -> List[Dict[str, Any]]:
            return [
                MCPToolDefinition.define_tool(
                    name="test_tool",
                    description="A test tool",
                    parameters={
                        "query": {
                            "type": "string",
                            "description": "Test query"
                        }
                    },
                    required=["query"]
                )
            ]
    
    # Initialize (will use application default credentials)
    try:
        server = TestMCPServer(project_id="test-project")
        print("Server initialized successfully")
        print(f"Server info: {server.get_server_info()}")
    except AuthenticationError as e:
        print(f"Authentication error (expected in test): {e}")
