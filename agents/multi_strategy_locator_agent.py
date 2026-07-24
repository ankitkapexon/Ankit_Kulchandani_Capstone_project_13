"""Enhanced locator agent with multi-strategy support for self-healing.

Generates multiple fallback locator strategies per element to enable
robust, self-healing test automation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.locator_agent import LocatorAgent
from config.app_config import AppConfig, get_config

logger = logging.getLogger(__name__)


class MultiStrategyLocatorAgent(LocatorAgent):
    """Enhanced locator agent that generates multiple strategies per element."""
    
    def __init__(
        self,
        project_root: Optional[Path | str] = None,
        config: Optional[AppConfig] = None,
    ):
        """Initialize multi-strategy locator agent.
        
        Args:
            project_root: Project root directory path
        """
        resolved_config = config or get_config()
        super().__init__(project_root=project_root, config=resolved_config)
    
    def _build_locator_entry(
        self,
        element: Dict[str, Any],
        action: str,
        step: str
    ) -> Dict[str, Any]:
        """Build enhanced locator entry with multiple strategies.
        
        Args:
            element: SSM element dictionary
            action: Inferred action (tap, type, verify, scroll)
            step: Original test step text
        
        Returns:
            Locator entry with primary and fallback strategies
        """
        element_label = element.get("label") or element.get("id") or "unknown"
        element_type = element.get("type", "unknown")
        confidence = element.get("confidence")
        
        # Generate all possible locator strategies
        strategies = self._generate_all_strategies(element)
        
        # Separate primary from fallbacks
        primary_strategy = strategies[0] if strategies else {
            "type": "text",
            "value": element_label,
            "priority": 5,
            "reliability": 0.5
        }
        
        fallback_strategies = strategies[1:] if len(strategies) > 1 else []
        
        return {
            "element": element_label,
            "element_type": element_type,
            "action": action,
            "step_description": step,
            "confidence": confidence,
            
            # Multi-strategy for self-healing
            "primary_strategy": primary_strategy,
            "fallback_strategies": fallback_strategies,
            
            # Deprecated (for backward compatibility)
            "locator_strategy": primary_strategy["type"],
            "locator_value": primary_strategy["value"],
        }
    
    def _generate_all_strategies(self, element: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate all possible locator strategies for an element.
        
        Strategies are returned in priority order:
        1. Resource ID (most stable)
        2. Accessibility ID
        3. Content Description
        4. Text/Label
        5. Class + Index (last resort)
        
        Args:
            element: SSM element dictionary
        
        Returns:
            List of strategy dictionaries with type, value, priority, reliability
        """
        strategies = []
        element_label = element.get("label", "")
        element_id = element.get("id")
        element_type = element.get("type", "unknown")
        metadata = element.get("metadata", {})
        
        # Strategy 1: Resource ID (highest priority, most stable)
        resource_id = metadata.get("resource_id") or self._infer_resource_id(
            element_label,
            element_type
        )
        if resource_id:
            strategies.append({
                "type": "resource_id",
                "value": resource_id,
                "priority": 1,
                "reliability": 0.95,
                "description": "Android resource ID (most stable)"
            })
        
        # Strategy 2: Accessibility ID
        accessibility_id = metadata.get("accessibility_id") or metadata.get("content_desc")
        if accessibility_id:
            strategies.append({
                "type": "accessibility_id",
                "value": accessibility_id,
                "priority": 2,
                "reliability": 0.90,
                "description": "Accessibility identifier"
            })
        
        # Strategy 3: Content Description (for Android)
        content_desc = metadata.get("content_desc")
        if content_desc and content_desc != accessibility_id:
            strategies.append({
                "type": "content_desc",
                "value": content_desc,
                "priority": 3,
                "reliability": 0.85,
                "description": "Content description attribute"
            })
        
        # Strategy 4: Text-based (works if text doesn't change)
        if element_label:
            strategies.append({
                "type": "text",
                "value": element_label,
                "priority": 4,
                "reliability": 0.75,
                "description": "Visible text content"
            })
        
        # Strategy 5: Class name + text combination
        if element_type != "unknown":
            class_name = self._map_type_to_class(element_type)
            if class_name:
                strategies.append({
                    "type": "class_text",
                    "value": f"{class_name}:{element_label}",
                    "priority": 5,
                    "reliability": 0.70,
                    "description": "Class name with text filter"
                })
        
        # Strategy 6: XPath (last resort, least stable)
        # Only add if we have something to search for
        if element_label:
            xpath = self._generate_xpath(element_label, element_type, metadata)
            if xpath:
                strategies.append({
                    "type": "xpath",
                    "value": xpath,
                    "priority": 6,
                    "reliability": 0.60,
                    "description": "XPath selector (least stable)"
                })
        
        # If no strategies were generated, add a default text-based one
        if not strategies:
            strategies.append({
                "type": "text",
                "value": element_label or element_id or "unknown",
                "priority": 10,
                "reliability": 0.50,
                "description": "Fallback text selector"
            })
        
        return strategies
    
    def _infer_resource_id(self, label: str, element_type: str) -> Optional[str]:
        """Infer likely resource ID based on label and type.
        
        Args:
            label: Element label
            element_type: Element type
        
        Returns:
            Inferred resource ID or None
        """
        # Common patterns for SauceLabs demo app
        app_package = "com.saucelabs.mydemoapp.android"
        
        label_lower = label.lower() if label else ""
        
        # Login screen
        if "username" in label_lower:
            return f"{app_package}:id/nameET"
        if "password" in label_lower:
            return f"{app_package}:id/passwordET"
        if "login" in label_lower and element_type == "button":
            return f"{app_package}:id/loginBtn"
        
        # Navigation
        if "menu" in label_lower:
            return f"{app_package}:id/menuIV"
        if "cart" in label_lower and "icon" in label_lower:
            return f"{app_package}:id/cartIV"
        
        # Cart screen
        if "checkout" in label_lower:
            return f"{app_package}:id/checkoutBtn"
        if "remove" in label_lower and "item" in label_lower:
            return f"{app_package}:id/removeBtn"
        
        # Product screens
        if "add to cart" in label_lower:
            return f"{app_package}:id/addToCartBtn"
        if "product" in label_lower and ("image" in label_lower or "picture" in label_lower):
            return f"{app_package}:id/productIV"
        
        return None
    
    def _map_type_to_class(self, element_type: str) -> Optional[str]:
        """Map SSM element type to Android class name.
        
        Args:
            element_type: SSM element type
        
        Returns:
            Android class name or None
        """
        type_mapping = {
            "button": "android.widget.Button",
            "textfield": "android.widget.EditText",
            "label": "android.widget.TextView",
            "text": "android.widget.TextView",
            "image": "android.widget.ImageView",
            "checkbox": "android.widget.CheckBox",
            "icon_button": "android.widget.ImageButton",
        }
        
        return type_mapping.get(element_type.lower())
    
    def _generate_xpath(
        self,
        label: str,
        element_type: str,
        metadata: Dict[str, Any]
    ) -> Optional[str]:
        """Generate XPath selector for element.
        
        Args:
            label: Element label
            element_type: Element type
            metadata: Element metadata
        
        Returns:
            XPath string or None
        """
        class_name = self._map_type_to_class(element_type)
        
        if not class_name:
            # Generic XPath by text
            return f'//*[@text="{label}"]'
        
        # XPath with class and text
        return f'//{class_name}[@text="{label}"]'
    
    def run(self, base_dir: Optional[Path | str] = None) -> List[Path]:
        """Run multi-strategy locator generation on all artifact files.
        
        Args:
            base_dir: Project root directory
        
        Returns:
            List of generated locator file paths
        """
        if base_dir:
            self.project_root = Path(base_dir)
        
        ssm_dir = self.project_root / "artifacts" / "ssm_json_output"
        manual_dir = self.project_root / "artifacts" / "manual_testcases"
        output_dir = self.project_root / "artifacts" / "locator_output"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not ssm_dir.exists():
            logger.error(f"SSM directory not found: {ssm_dir}")
            return []
        
        ssm_files = sorted(ssm_dir.glob("*.json"))
        if not ssm_files:
            logger.warning(f"No SSM files found in {ssm_dir}")
            return []
        
        logger.info(f"Found {len(ssm_files)} SSM files to process")
        
        generated_files = []
        
        for ssm_file in ssm_files:
            try:
                # Load SSM data
                ssm_data = json.loads(ssm_file.read_text(encoding="utf-8"))
                screen_name = str(ssm_data.get("screen_name", "unknown"))
                screen_token = self._slugify(screen_name)
                
                # Find matching test case file (if exists)
                test_case_files = list(manual_dir.glob(f"*{screen_name}*.txt"))
                if not test_case_files:
                    test_case_files = list(manual_dir.glob(f"*{screen_token}*.txt"))
                test_case_text = ""
                if test_case_files:
                    test_case_text = test_case_files[0].read_text(encoding="utf-8")
                
                # Generate multi-strategy locators
                locator_data = self.generate_locators(ssm_data, test_case_text)
                
                # Save to output file
                output_file = output_dir / f"locator_{screen_token}.json"
                output_file.write_text(
                    json.dumps(locator_data, indent=2),
                    encoding="utf-8"
                )
                
                logger.info(f"✓ Generated multi-strategy locators for {screen_name} → {output_file.name}")
                generated_files.append(output_file)
                
            except Exception as e:
                logger.error(f"Failed to process {ssm_file.name}: {e}")
                continue
        
        logger.info(f"Successfully generated {len(generated_files)} locator files with multi-strategy support")
        return generated_files
