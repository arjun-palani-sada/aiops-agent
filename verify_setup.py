#!/usr/bin/env python3
"""Verification script to test AIOps Agent installation"""

import sys
import os

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def check_python():
    """Check Python version"""
    print_header("1. Python Version")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major >= 3 and version.minor >= 10:
        print("✅ Python 3.10+ detected")
        return True
    print("❌ Python 3.10+ required")
    return False

def check_files():
    """Check required files exist"""
    print_header("2. File Structure")
    
    files = [
        "src/__init__.py",
        "src/core/__init__.py",
        "src/core/state.py",
        "src/core/utils.py",
        "src/mcp/__init__.py",
        "src/mcp/mcp_base.py",
        "src/mcp/gcp_monitoring.py",
        "src/agents/__init__.py",
        "requirements.txt",
        "setup.py",
    ]
    
    missing = []
    for f in files:
        if os.path.exists(f):
            print(f"✅ {f}")
        else:
            print(f"❌ {f} MISSING")
            missing.append(f)
    
    return len(missing) == 0

def check_dependencies():
    """Check if dependencies are installed"""
    print_header("3. Dependencies")
    
    deps = [
        ("pydantic", "pydantic"),
        ("yaml", "pyyaml"),
        ("google.cloud.monitoring_v3", "google-cloud-monitoring"),
        ("google.cloud.logging", "google-cloud-logging"),
    ]
    
    missing = []
    for module, package in deps:
        try:
            __import__(module)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - Run: pip install {package}")
            missing.append(package)
    
    return len(missing) == 0

def check_imports():
    """Check if package imports work"""
    print_header("4. Package Imports")
    
    tests = []
    
    # Test src package
    try:
        import src
        print(f"✅ import src")
        tests.append(True)
    except ImportError as e:
        print(f"❌ import src failed: {e}")
        print("   Run: pip install -e .")
        tests.append(False)
        return False
    
    # Test core
    try:
        from src.core import StateManager, InvestigationState
        print("✅ from src.core import StateManager, InvestigationState")
        tests.append(True)
    except ImportError as e:
        print(f"❌ core imports failed: {e}")
        tests.append(False)
    
    # Test MCP
    try:
        from src.mcp import BaseMCPServer, GCPMonitoringServer
        print("✅ from src.mcp import BaseMCPServer, GCPMonitoringServer")
        tests.append(True)
    except ImportError as e:
        print(f"❌ mcp imports failed: {e}")
        tests.append(False)
    
    return all(tests)

def check_functionality():
    """Test basic functionality"""
    print_header("5. Functionality Test")
    
    try:
        from src.core import StateManager
        
        state = StateManager.create_initial_state(
            intent="app_crash",
            service_name="test-app",
            user_query="Test query"
        )
        
        print(f"✅ Created investigation state")
        print(f"   Service: {state.service_name}")
        print(f"   Intent: {state.intent.value}")
        return True
        
    except Exception as e:
        print(f"❌ Functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all checks"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║        AIOps Agent - Installation Verification          ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    results = {
        "Python Version": check_python(),
        "File Structure": check_files(),
        "Dependencies": check_dependencies(),
        "Package Imports": check_imports(),
        "Functionality": check_functionality(),
    }
    
    print_header("Summary")
    
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:12} {name}")
    
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    print(f"\n{'='*60}")
    print(f"  {passed_count}/{total_count} checks passed")
    print('='*60)
    
    if passed_count == total_count:
        print("""
✅ SUCCESS! Your AIOps Agent is ready!

Next steps:
  1. Read README.md for overview
  2. Check NEXT_STEPS.md for implementation guide
  3. Start building the GCP Logging MCP server

Happy coding! 🚀
        """)
        return 0
    else:
        print("""
❌ Setup incomplete. Please fix the issues above.

Common fixes:
  1. Install dependencies: pip install -r requirements.txt
  2. Install package: pip install -e .
  3. Activate virtual environment
        """)
        return 1

if __name__ == "__main__":
    sys.exit(main())
