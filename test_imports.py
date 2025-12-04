#!/usr/bin/env python3
"""Quick test to verify all imports work"""

print("Testing imports...")

try:
    print("1. Testing src package...")
    import src
    print("   ✅ import src")
    
    print("\n2. Testing core module...")
    from src.core import StateManager, InvestigationState
    print("   ✅ from src.core import StateManager, InvestigationState")
    
    print("\n3. Testing MCP module...")
    from src.mcp import BaseMCPServer, GCPMonitoringServer
    print("   ✅ from src.mcp import BaseMCPServer, GCPMonitoringServer")
    
    print("\n4. Creating a test state...")
    state = StateManager.create_initial_state(
        intent="app_crash",
        service_name="test-app"
    )
    print(f"   ✅ Created state for: {state.service_name}")
    print(f"   ✅ Intent: {state.intent.value}")
    
    print("\n" + "="*60)
    print("🎉 SUCCESS! All imports working correctly!")
    print("="*60)
    print("\nYou're ready to start building!")
    print("\nNext: Run 'python verify_setup.py' for full verification")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nFix: Run 'pip install -e .' in the project directory")
    import traceback
    traceback.print_exc()
