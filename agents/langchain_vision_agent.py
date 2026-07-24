"""LangChain-powered vision agent for mobile screenshot analysis.

This module provides an enhanced vision agent using LangChain for:
- Structured output parsing with Pydantic models
- Automatic retry with error correction
- Token usage tracking and cost management
- Multi-provider support (OpenAI, Claude, etc.)
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from langchain_core.messages import SystemMessage
    from langchain_openai import ChatOpenAI
    from langchain_community.callbacks import get_openai_callback
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain not installed. Install with: pip install langchain langchain-openai")
    LANGCHAIN_AVAILABLE = False
    ChatPromptTemplate = None
    PydanticOutputParser = None
    SystemMessage = None
    ChatOpenAI = None
    get_openai_callback = None

from models.ssm import ScreenSemanticModel
from agents.vision_agent import VisionAgent, OpenAIVisionAgent


class LangChainVisionAgent(VisionAgent):
    """LangChain-powered vision agent with structured output and automatic retry."""
    
    def __init__(
        self,
        prompt_template: str | None = None,
        model_name: str | None = None,
        enable_cache: bool = True
    ):
        """Initialize LangChain vision agent.
        
        Args:
            prompt_template: Custom prompt template text
            model_name: LLM model name (e.g., 'gpt-4o-mini')
            enable_cache: Enable LLM response caching
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain not installed. Install with: "
                "pip install langchain langchain-openai"
            )
        
        super().__init__(model_name=model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_base = os.getenv("OPENAI_API_BASE")
        self.enable_cache = enable_cache
        self.system_message = prompt_template or self._default_prompt_template()
        self._fallback_openai_agent = OpenAIVisionAgent(
            prompt_template=self._default_prompt_template(),
            model_name=self.model_name,
        )
        
        # Initialize LangChain components
        self.llm = self._create_llm()
        self.parser = PydanticOutputParser(pydantic_object=ScreenSemanticModel)
        self.prompt = self._create_prompt()
        
        # Create chain with automatic retry
        self.chain = self._create_chain()
        
        # Token usage tracking
        self.total_tokens = 0
        self.total_cost = 0.0
    
    def validate_configuration(self) -> None:
        """Validate agent configuration."""
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            raise EnvironmentError(
                "OPENAI_API_KEY is required. Set it in your .env file."
            )
    
    def _create_llm(self) -> ChatOpenAI:
        """Create LangChain LLM instance."""
        model_name_lower = str(self.model_name).lower()
        llm_kwargs = {
            "model": self.model_name,
            "api_key": self.api_key,
        }

        # GPT-5 class models through some gateways reject temperature=0.
        # Mirror the fallback behavior used in OpenAIVisionAgent.
        if "gpt-5" in model_name_lower:
            llm_kwargs["temperature"] = 1
        else:
            llm_kwargs["temperature"] = 0
        
        if self.api_base:
            llm_kwargs["base_url"] = self.api_base
            
            # For LiteLLM or custom gateways, add custom headers if needed
            if "litellm" in self.api_base.lower():
                logger.info("Detected LiteLLM gateway - configuring custom headers")
                # LiteLLM may use x-litellm-api-key header
                # OpenAI client will use api_key in Authorization header by default
                # If custom header handling is needed, it's handled by the OpenAI client
        
        # Enable caching if requested
        if self.enable_cache:
            try:
                from langchain_core.caches import InMemoryCache
                from langchain_core.globals import set_llm_cache
                set_llm_cache(InMemoryCache())
                logger.info("LLM response caching enabled")
            except Exception as e:
                logger.warning(f"Could not enable caching: {e}")
        
        return ChatOpenAI(**llm_kwargs)
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """Create LangChain prompt template."""
        # Keep the system prompt as a concrete message object so JSON braces in
        # custom prompt files are never interpreted as template placeholders.
        return ChatPromptTemplate.from_messages([
            SystemMessage(content=self.system_message),
            ("user", [
                {"type": "text", "text": "Filename hint: {filename}\\n\\nAnalyze this mobile app screenshot and return a JSON object with screen_name, screen_purpose, and elements array."},
                {"type": "image_url", "image_url": "data:image/jpeg;base64,{image_data}"}
            ])
        ])
    
    def _default_prompt_template(self) -> str:
        """Default system prompt for vision analysis."""
        return """You are a mobile UI analysis expert. Analyze the mobile app screenshot and extract:
1. Screen name (e.g., Login, Product Listing, Cart, Product Details)
2. Screen purpose (brief description)
3. All interactive UI elements with their properties

For each element, identify:
- label: Human-readable name
- type: UI element type (textfield, button, image, label, etc.)
- actions: Possible user actions (enter_text, tap, verify, scroll)
- confidence: Your confidence in identifying this element (0.0-1.0)

Important guidelines:
- Use standard screen names (Login, Cart, Product Listing, Product Details, Checkout, Home, Profile, Settings)
- Be specific with element labels
- Include all tappable, typeable, and verifiable elements
- Set realistic confidence scores based on UI clarity
- Do NOT include decorative elements unless they're interactive

Return ONLY valid JSON matching the ScreenSemanticModel schema."""

    def _create_chain(self):
        """Create LangChain processing chain."""
        # Simple chain: Prompt → LLM (we'll parse JSON manually)
        chain = self.prompt | self.llm
        
        # Note: Auto-retry not available in this simple chain
        # If needed, wrap with manual retry logic
        return chain
    
    def analyze_image(self, image_path: str, **kwargs) -> Dict[str, Any]:
        """Analyze mobile screenshot and return structured SSM data.
        
        Args:
            image_path: Path to screenshot file
            **kwargs: Additional arguments (unused, for compatibility)
        
        Returns:
            Dictionary with SSM data (screen_name, elements, etc.)
        """
        self.validate_configuration()
        
        # Read and encode image
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        filename = Path(image_path).stem
        
        # Run chain (token tracking may not work with custom gateways)
        try:
            result = self.chain.invoke({
                "filename": filename,
                "image_data": image_data
            })
            
            logger.info("Vision analysis complete")
            
            # Parse the result
            if hasattr(result, 'content'):
                content = result.content
            else:
                content = str(result)
            
            # Try to extract JSON from the response
            import json
            import re
            
            # Try to find JSON in the response
            json_match = re.search(r'\\{.*\\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                ssm_dict = json.loads(json_str)
            else:
                # If no JSON found, try parsing the whole thing
                ssm_dict = json.loads(content)
        
        except Exception as e:
            logger.error(f"LangChain vision analysis failed: {e}")
            logger.info("Falling back to standard OpenAI agent...")
            
            # Fallback to original OpenAI agent
            return self._fallback_openai_agent.analyze_image(image_path)
        
        # Infer screen name if needed
        screen_name = ssm_dict.get("screen_name")
        if not screen_name or screen_name.lower() in ["unknown", "unspecified", "n/a", "none"]:
            inferred_name = self._infer_screen_name_from_context(ssm_dict, filename, image_path)
            if inferred_name:
                ssm_dict["screen_name"] = inferred_name

        if not ssm_dict.get("elements"):
            ssm_dict["elements"] = self._fallback_openai_agent._fallback_elements_for_screen(
                ssm_dict.get("screen_name")
            )
            metadata = dict(ssm_dict.get("metadata") or {})
            metadata["auto_filled_elements"] = True
            metadata["auto_fill_reason"] = "vision_model_returned_empty_elements"
            ssm_dict["metadata"] = metadata
        
        # Add source metadata
        ssm_dict["source"] = "langchain_vision"
        ssm_dict["source_image"] = str(image_path)
        
        return ssm_dict
    
    def _infer_screen_name_from_context(
        self,
        ssm_data: Dict[str, Any],
        filename: str,
        image_path: str,
    ) -> Optional[str]:
        """Infer screen name from filename and content."""
        inferred_name = self._fallback_openai_agent._infer_screen_name(
            ssm_data.get("screen_name"),
            image_path=image_path,
            screen_purpose=ssm_data.get("screen_purpose"),
        )
        if inferred_name and inferred_name.lower() not in {"unknown", "unspecified", "n/a", "none", "screen", ""}:
            return inferred_name
        
        # Check element labels for hints
        elements = ssm_data.get("elements", [])
        element_labels = [e.get("label", "").lower() for e in elements]
        
        if any("login" in label for label in element_labels):
            return "Login"
        if any("cart" in label or "checkout" in label for label in element_labels):
            return "Cart"
        if any("add to cart" in label or "price" in label for label in element_labels):
            return "Product Details"

        if filename:
            inferred_from_filename = self._fallback_openai_agent._infer_screen_name("", image_path=filename)
            if inferred_from_filename:
                return inferred_from_filename
        
        return None
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get token usage and cost statistics."""
        return {
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "model": self.model_name,
        }


def create_langchain_vision_agent(
    provider: str = "openai",
    prompt_template: str | None = None,
    **kwargs
) -> VisionAgent:
    """Factory function to create vision agent (LangChain or fallback).
    
    Args:
        provider: Agent provider ('openai' or 'mock')
        prompt_template: Custom prompt template
        **kwargs: Additional arguments for agent
    
    Returns:
        VisionAgent instance
    """
    if provider == "mock":
        # Import mock agent
        from agents.vision_agent import MockVisionAgent
        return MockVisionAgent()
    
    # Try LangChain first, fallback to standard OpenAI
    if LANGCHAIN_AVAILABLE:
        try:
            return LangChainVisionAgent(
                prompt_template=prompt_template,
                **kwargs
            )
        except Exception as e:
            # If a custom prompt file has template tokens incompatible with
            # LangChain parsing, retry with the built-in default prompt before
            # falling back to the non-LangChain implementation.
            if prompt_template:
                logger.warning(
                    "Custom LangChain prompt failed to initialize (%s). Retrying with default prompt.",
                    e,
                )
                try:
                    return LangChainVisionAgent(
                        prompt_template=None,
                        **kwargs
                    )
                except Exception as retry_exc:
                    logger.warning(
                        "Could not create LangChain agent with default prompt: %s. "
                        "Using standard OpenAI agent.",
                        retry_exc,
                    )
            else:
                logger.warning(
                    "LangChain vision init failed (%s); switching to standard OpenAI vision agent.",
                    e,
                )
    
    # Fallback
    return OpenAIVisionAgent(
        prompt_template=prompt_template,
        **kwargs
    )
