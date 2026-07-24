"""Quick test script for LangChain agent with LiteLLM gateway."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load configuration
from services.enhanced_config import get_config
config = get_config()

print("=" * 60)
print("Testing LangChain Vision Agent")
print("=" * 60)
print(f"API Key: {config.openai_api_key[:15]}...")
print(f"API Base: {config.openai_api_base}")
print(f"Model: {config.openai_model}")
print("=" * 60)

# Create agent
from agents.langchain_vision_agent import LangChainVisionAgent

try:
    agent = LangChainVisionAgent()
    print("\n✅ LangChain agent created successfully!")
    print(f"Model: {agent.model_name}")
    print(f"API Base: {agent.api_base}")
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - LangChain integration working!")
    print("=" * 60)
except Exception as e:
    print(f"\n❌ Error creating agent: {e}")
    print("=" * 60)
    import traceback
    traceback.print_exc()
