"""Custom OpenAI client wrapper for LiteLLM and other custom gateways.

Handles custom headers like x-litellm-api-key while maintaining
compatibility with standard OpenAI API.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    logger.warning("OpenAI package not installed")
    OpenAI = None
    OPENAI_AVAILABLE = False


class CustomGatewayClient:
    """OpenAI client wrapper with custom header support for LiteLLM gateways."""
    
    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """Initialize custom gateway client.
        
        Args:
            api_key: API key for authentication
            base_url: Custom API base URL (e.g., LiteLLM gateway)
            custom_headers: Additional headers to include in requests
            **kwargs: Additional arguments passed to OpenAI client
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")
        
        self.api_key = api_key
        self.base_url = base_url
        self.custom_headers = custom_headers or {}
        
        # Create OpenAI client with custom configuration
        client_kwargs = {
            "api_key": api_key,
            **kwargs
        }
        
        if base_url:
            client_kwargs["base_url"] = base_url
        
        # Add custom headers if provided
        if self.custom_headers:
            # For LiteLLM, the API key might go in a custom header
            if "x-litellm-api-key" in self.custom_headers:
                # Some gateways use custom headers for auth
                default_headers = {
                    "x-litellm-api-key": api_key,
                    **self.custom_headers
                }
                client_kwargs["default_headers"] = default_headers
        
        self.client = OpenAI(**client_kwargs)
        
        logger.info(f"Custom gateway client initialized with base_url: {base_url}")
    
    @property
    def chat(self):
        """Access to chat completions API."""
        return self.client.chat
    
    @property
    def completions(self):
        """Access to completions API."""
        return self.client.completions
    
    def __getattr__(self, name):
        """Forward all other attributes to underlying OpenAI client."""
        return getattr(self.client, name)


def create_openai_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None
) -> OpenAI:
    """Factory function to create OpenAI client with custom gateway support.
    
    Args:
        api_key: API key (defaults to OPENAI_API_KEY env var)
        base_url: Custom API base URL (defaults to OPENAI_API_BASE env var)
        custom_headers: Custom headers for gateway authentication
    
    Returns:
        OpenAI client instance (wrapped if custom headers needed)
    """
    if not OPENAI_AVAILABLE:
        raise ImportError("OpenAI package not installed. Install with: pip install openai")
    
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    base_url = base_url or os.getenv("OPENAI_API_BASE")
    
    if not api_key:
        raise ValueError("API key is required. Set OPENAI_API_KEY environment variable.")
    
    # Check if custom headers are needed
    custom_headers_env = os.getenv("CUSTOM_LLM_HEADERS", "")
    if custom_headers_env:
        # Parse custom headers from env var
        # Format: "header1=value1,header2=value2"
        if not custom_headers:
            custom_headers = {}
        for header_pair in custom_headers_env.split(","):
            if "=" in header_pair:
                key, value = header_pair.split("=", 1)
                custom_headers[key.strip()] = value.strip()
    
    # Use custom wrapper if custom headers are needed
    if custom_headers or (base_url and "litellm" in base_url.lower()):
        logger.info("Using custom gateway client with special headers")
        return CustomGatewayClient(
            api_key=api_key,
            base_url=base_url,
            custom_headers=custom_headers
        )
    
    # Standard OpenAI client
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    
    return OpenAI(**client_kwargs)


def test_gateway_connection(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: str = "gpt-3.5-turbo"
) -> Dict[str, Any]:
    """Test connection to OpenAI or custom gateway.
    
    Args:
        api_key: API key to test
        base_url: Custom gateway URL to test
        model: Model to use for test request
    
    Returns:
        Dictionary with test results
    """
    try:
        client = create_openai_client(api_key=api_key, base_url=base_url)
        
        # Make a simple test request
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        
        return {
            "success": True,
            "model": response.model,
            "message": "Gateway connection successful",
            "response": response.choices[0].message.content
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Gateway connection failed: {e}"
        }


if __name__ == "__main__":
    # Test gateway connection when run directly
    import sys
    from pathlib import Path
    
    # Add project root to path
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    try:
        from services.enhanced_config import get_config
        config = get_config()
        
        print("=" * 60)
        print("Testing LiteLLM Gateway Connection")
        print("=" * 60)
        print(f"API Base: {config.openai_api_base}")
        print(f"Model: {config.openai_model}")
        print("=" * 60)
        
        result = test_gateway_connection(
            api_key=config.openai_api_key,
            base_url=config.openai_api_base,
            model=config.openai_model
        )
        
        if result["success"]:
            print("✅ SUCCESS!")
            print(f"Model: {result['model']}")
            print(f"Response: {result['response']}")
        else:
            print("❌ FAILED!")
            print(f"Error: {result['error']}")
        
        print("=" * 60)
        
    except ImportError as e:
        print("❌ FAILED!")
        print(f"Import Error: {e}")
        print("\nPlease run: pip install -r requirements.txt")
        print("=" * 60)
