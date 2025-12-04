"""
Configuration Loader - Loads environment variables from .env file

This ensures all scripts can read from .env without manual exports.
"""

import os
from pathlib import Path
from typing import Optional


def load_env_config():
    """
    Load environment variables from .env file
    
    Looks for .env file in:
    1. Current directory
    2. Parent directory
    3. Project root
    """
    try:
        from dotenv import load_dotenv
        
        # Find .env file
        current_dir = Path.cwd()
        env_locations = [
            current_dir / ".env",                    # Current directory
            current_dir.parent / ".env",             # Parent directory
            Path(__file__).parent.parent / ".env",   # Project root
        ]
        
        for env_path in env_locations:
            if env_path.exists():
                load_dotenv(env_path)
                print(f"✅ Loaded environment from: {env_path}")
                return True
        
        print("⚠️  No .env file found. Using system environment variables.")
        return False
        
    except ImportError:
        print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
        print("   Using system environment variables only.")
        return False


def get_required_config(key: str, default: Optional[str] = None) -> str:
    """
    Get required configuration value
    
    Args:
        key: Environment variable name
        default: Default value if not found
        
    Returns:
        Configuration value
        
    Raises:
        ValueError: If required config is missing and no default provided
    """
    value = os.environ.get(key, default)
    
    if value is None:
        raise ValueError(
            f"Required configuration '{key}' not found in environment. "
            f"Either set it with 'export {key}=...' or add to .env file."
        )
    
    return value


def get_config(key: str, default: str = "") -> str:
    """
    Get optional configuration value
    
    Args:
        key: Environment variable name
        default: Default value if not found
        
    Returns:
        Configuration value or default
    """
    return os.environ.get(key, default)


# Configuration keys
class Config:
    """Centralized configuration"""
    
    @staticmethod
    def load():
        """Load all configuration"""
        load_env_config()
    
    @staticmethod
    def get_google_api_key() -> Optional[str]:
        """Get Google API key"""
        return os.environ.get("GOOGLE_API_KEY")
    
    @staticmethod
    def get_model_name() -> str:
        """Get model name (default: gemini-pro)"""
        return os.environ.get("MODEL_NAME", "gemini-pro")
    
    @staticmethod
    def get_gcp_project_id() -> Optional[str]:
        """Get GCP project ID"""
        return os.environ.get("GCP_PROJECT_ID")
    
    @staticmethod
    def use_llm() -> bool:
        """Check if LLM should be used"""
        use_llm = os.environ.get("USE_LLM", "false").lower()
        return use_llm in ["true", "1", "yes"]
    
    @staticmethod
    def is_configured() -> bool:
        """Check if minimum configuration exists"""
        return bool(Config.get_google_api_key())


# Auto-load on import
load_env_config()


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Configuration Status")
    print("="*70)
    
    Config.load()
    
    print(f"\n🔑 GOOGLE_API_KEY: {'✅ Set' if Config.get_google_api_key() else '❌ Not set'}")
    print(f"🤖 MODEL_NAME: {Config.get_model_name()}")
    print(f"☁️  GCP_PROJECT_ID: {Config.get_gcp_project_id() or '❌ Not set'}")
    print(f"🧠 USE_LLM: {Config.use_llm()}")
    
    if Config.is_configured():
        print(f"\n✅ Configuration complete!")
    else:
        print(f"\n⚠️  Missing required configuration:")
        print(f"   - Add GOOGLE_API_KEY to .env file")
        print(f"   - Or export GOOGLE_API_KEY='your-key'")
    
    print("\n" + "="*70)
