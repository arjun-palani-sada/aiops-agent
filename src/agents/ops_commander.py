"""
Ops Commander Agent (Agent 1)

Root orchestrator that classifies user intent and delegates to specialists.
This is the entry point for all user queries.
"""

import logging
from typing import Dict, Any, Optional

from .investigator import Investigator


class OpsCommander:
    """
    Agent 1: The Root Orchestrator

    Responsibilities:
    - Classify user intent
    - Delegate to appropriate specialist (currently: Investigator)
    - Return results to user

    Design Philosophy: "Black Box Delegation"
    - Does NOT perform investigations itself
    - Treats complex workflows as single tool calls
    - Keeps context window clean
    """

    def __init__(
            self,
            project_id: str,
            use_llm: bool = True
    ):
        """
        Initialize Ops Commander

        Args:
            project_id: GCP project ID
            use_llm: Whether to use LLM for intent classification and delegation
        """
        self.project_id = project_id
        self.use_llm = use_llm
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize the Investigator (our only tool for now)
        self.investigator = Investigator(project_id=project_id, use_llm=use_llm)

        # Future: Add more specialists here
        # self.network_troubleshooter = NetworkTroubleshooter(...)
        # self.cost_optimizer = CostOptimizer(...)

        self.logger.info("Ops Commander initialized")

        if use_llm:
            try:
                import google.generativeai as genai
                import os

                api_key = os.environ.get("GOOGLE_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    self.model = genai.GenerativeModel('gemini-1.5-flash')
                    self.logger.info("Using Gemini LLM for orchestration")
                else:
                    self.logger.warning("No GOOGLE_API_KEY, using rule-based")
                    self.use_llm = False
            except ImportError:
                self.logger.warning("google-generativeai not installed, using rules")
                self.use_llm = False

    def handle_query(
            self,
            user_query: str,
            service_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle user query - the main entry point

        Args:
            user_query: User's question or issue description
            service_name: Optional service name (extracted from query if not provided)

        Returns:
            Dict with response and metadata
        """
        self.logger.info(f"Handling query: {user_query[:100]}...")

        try:
            # Step 1: Classify intent
            intent = self._classify_intent(user_query)

            # Step 2: Extract service name if not provided
            if not service_name:
                service_name = self._extract_service_name(user_query)

            # Step 3: Route to appropriate handler
            if intent in ["app_crash", "app_error", "performance_issue", "app_issue"]:
                return self._handle_app_issue(user_query, service_name, intent)

            elif intent in ["connectivity_issue", "network_issue"]:
                # Future: Route to network troubleshooter
                return {
                    "success": False,
                    "message": "Network troubleshooting not yet implemented",
                    "suggestion": "Please check firewall rules and VPC configuration manually"
                }

            else:
                # Unknown intent - try to help anyway
                return self._handle_unknown_intent(user_query, service_name)

        except Exception as e:
            self.logger.error(f"Error handling query: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "An error occurred while processing your query"
            }

    def _classify_intent(self, user_query: str) -> str:
        """
        Classify user intent from query

        Args:
            user_query: User's question

        Returns:
            Intent type (app_crash, app_error, performance_issue, etc.)
        """
        query_lower = user_query.lower()

        # Rule-based classification (simple but effective)
        if any(word in query_lower for word in [
            "crash", "crashing", "crashed", "down", "not responding"
        ]):
            return "app_crash"

        elif any(word in query_lower for word in [
            "error", "exception", "failed", "failing", "broken"
        ]):
            return "app_error"

        elif any(word in query_lower for word in [
            "slow", "performance", "latency", "timeout", "hanging"
        ]):
            return "performance_issue"

        elif any(word in query_lower for word in [
            "connection", "connectivity", "network", "unreachable"
        ]):
            return "connectivity_issue"

        else:
            # Default to app_issue for investigation
            return "app_issue"

    def _extract_service_name(self, user_query: str) -> str:
        """
        Extract service name from query

        Args:
            user_query: User's question

        Returns:
            Service name or "unknown-service"
        """
        # Simple extraction - look for common patterns
        query_lower = user_query.lower()

        # Pattern: "my [service-name] is..."
        if " my " in query_lower:
            words = query_lower.split(" my ")[1].split()
            if words:
                return words[0].strip("'\",.!?")

        # Pattern: "[service-name] is..."
        words = query_lower.split()
        if words and len(words[0]) > 3:
            return words[0].strip("'\",.!?")

        # Default
        return "unknown-service"

    def _handle_app_issue(
            self,
            user_query: str,
            service_name: str,
            intent: str
    ) -> Dict[str, Any]:
        """
        Handle application issues by delegating to Investigator

        Args:
            user_query: User's question
            service_name: Service to investigate
            intent: Classified intent

        Returns:
            Investigation results
        """
        self.logger.info(f"Delegating to Investigator: {service_name} ({intent})")

        # Call the Investigator (black box delegation)
        result = self.investigator.investigate_app_health(
            service_name=service_name,
            intent=intent,
            user_query=user_query
        )

        # Add context for user
        if result["success"]:
            result["message"] = (
                f"I investigated {service_name} and found the following:"
            )
        else:
            result["message"] = (
                f"I couldn't complete the investigation for {service_name}. "
                f"Error: {result.get('error', 'Unknown error')}"
            )

        return result

    def _handle_unknown_intent(
            self,
            user_query: str,
            service_name: str
    ) -> Dict[str, Any]:
        """
        Handle queries with unknown intent

        Args:
            user_query: User's question
            service_name: Extracted service name

        Returns:
            Best-effort response
        """
        self.logger.info(f"Unknown intent, attempting generic investigation")

        # Try generic investigation anyway
        return self.investigator.investigate_app_health(
            service_name=service_name,
            intent="app_issue",
            user_query=user_query
        )


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO)

    project_id = os.environ.get("GCP_PROJECT_ID", "demo-project")

    # Initialize Ops Commander
    ops_commander = OpsCommander(project_id=project_id, use_llm=False)

    print("\n" + "=" * 70)
    print(" " * 15 + "🎯 AIOps Agent - Ops Commander")
    print("=" * 70)

    # Test cases
    test_queries = [
        ("My payment-api is crashing when processing refunds!", "payment-api"),
        ("The authentication service is throwing errors", "auth-service"),
        ("Why is my API so slow?", "api-service"),
        ("demo-app is not working", "demo-app"),
    ]

    for i, (query, expected_service) in enumerate(test_queries, 1):
        print(f"\n{'=' * 70}")
        print(f"Test Case {i}")
        print('=' * 70)
        print(f"\n💬 User Query: \"{query}\"")
        print(f"📍 Expected Service: {expected_service}")
        print("\n" + "-" * 70)

        result = ops_commander.handle_query(query)

        if result.get("success"):
            print(f"\n✅ SUCCESS")
            print(f"\n📊 Results:")
            print(f"   Service: {result.get('service_name')}")
            print(f"   Root Cause: {result.get('root_cause')}")
            print(f"   Confidence: {result.get('confidence', 0):.0%}")
            print(f"   Duration: {result.get('duration_seconds', 0):.2f}s")
            print(f"   Agents: {len(result.get('agent_sequence', []))}")

            # Show summary (first 3 lines)
            if 'summary' in result:
                summary_lines = result['summary'].split('\n')[:5]
                print(f"\n📝 Summary Preview:")
                for line in summary_lines:
                    print(f"   {line}")
                print("   ...")
        else:
            print(f"\n❌ FAILED")
            print(f"   Error: {result.get('error', 'Unknown')}")
            print(f"   Message: {result.get('message')}")

    # Interactive mode demo
    print("\n" + "=" * 70)
    print("\n🎮 Interactive Mode Demo")
    print("=" * 70)
    print("\nYou can now use the Ops Commander like this:\n")
    print("```python")
    print("from src.agents.ops_commander import OpsCommander")
    print("")
    print("commander = OpsCommander(project_id='your-project')")
    print("result = commander.handle_query('My app is crashing!')")
    print("print(result['summary'])")
    print("```")

    print("\n" + "=" * 70)
    print("✅ Ops Commander Ready!")
    print("=" * 70)
    print("\nYour AIOps Agent is COMPLETE and ready to use! 🎉")