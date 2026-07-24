"""Self-healing capabilities for Appium test automation.

Provides intelligent element location with automatic fallback strategies,
AI-powered healing when locators fail, and learning from historical data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.common.exceptions import NoSuchElementException, TimeoutException
    from selenium.webdriver.remote.webelement import WebElement
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    logger.warning("Appium/Selenium not installed. Self-healing features will be limited.")
    AppiumBy = None
    NoSuchElementException = Exception
    TimeoutException = Exception
    WebElement = Any
    EC = None
    WebDriverWait = None


class LocatorStrategy:
    """Represents a single locator strategy with metadata."""
    
    def __init__(
        self,
        strategy_type: str,
        value: str,
        priority: int = 5,
        reliability: float = 0.5,
        element_name: str = ""
    ):
        self.type = strategy_type
        self.value = value
        self.priority = priority
        self.reliability = reliability
        self.element_name = element_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "type": self.type,
            "value": self.value,
            "priority": self.priority,
            "reliability": self.reliability,
            "element_name": self.element_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LocatorStrategy:
        """Create from dictionary."""
        return cls(
            strategy_type=data.get("type", "text"),
            value=data.get("value", ""),
            priority=data.get("priority", 5),
            reliability=data.get("reliability", 0.5),
            element_name=data.get("element_name", "")
        )


class HealingRepository:
    """Stores and learns from element location attempts and healing events."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize healing repository with SQLite database.
        
        Args:
            db_path: Path to SQLite database file. Auto-created if not exists.
        """
        if db_path is None:
            db_path = Path("artifacts/healing_repository.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
    
    def _init_database(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            
            # Locator attempts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS locator_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    element_name TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    strategy_value TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    execution_time_ms INTEGER,
                    screen_name TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Healing events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS healing_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    element_name TEXT NOT NULL,
                    original_strategy TEXT NOT NULL,
                    healed_strategy TEXT NOT NULL,
                    healing_method TEXT,
                    success BOOLEAN NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Reliability scores table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reliability_scores (
                    strategy_hash TEXT PRIMARY KEY,
                    element_name TEXT NOT NULL,
                    strategy_type TEXT NOT NULL,
                    strategy_value TEXT NOT NULL,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    reliability_score REAL DEFAULT 0.5,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info(f"Healing repository initialized at {self.db_path}")
    
    def _get_strategy_hash(self, strategy: LocatorStrategy) -> str:
        """Generate unique hash for a locator strategy."""
        content = f"{strategy.element_name}:{strategy.type}:{strategy.value}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def record_attempt(
        self,
        strategy: LocatorStrategy,
        success: bool,
        execution_time_ms: int = 0,
        screen_name: str = ""
    ) -> None:
        """Record a locator attempt (success or failure)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            
            # Insert attempt record
            cursor.execute("""
                INSERT INTO locator_attempts 
                (element_name, strategy_type, strategy_value, success, execution_time_ms, screen_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                strategy.element_name,
                strategy.type,
                strategy.value,
                success,
                execution_time_ms,
                screen_name
            ))
            
            # Update reliability score
            strategy_hash = self._get_strategy_hash(strategy)
            
            # Get current scores
            cursor.execute("""
                SELECT success_count, failure_count FROM reliability_scores
                WHERE strategy_hash = ?
            """, (strategy_hash,))
            
            row = cursor.fetchone()
            if row:
                success_count, failure_count = row
                if success:
                    success_count += 1
                else:
                    failure_count += 1
            else:
                success_count = 1 if success else 0
                failure_count = 0 if success else 1
            
            # Calculate new reliability score
            total = success_count + failure_count
            reliability = success_count / total if total > 0 else 0.5
            
            # Upsert reliability score
            cursor.execute("""
                INSERT OR REPLACE INTO reliability_scores
                (strategy_hash, element_name, strategy_type, strategy_value, 
                 success_count, failure_count, reliability_score, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_hash,
                strategy.element_name,
                strategy.type,
                strategy.value,
                success_count,
                failure_count,
                reliability,
                datetime.now()
            ))
            
            conn.commit()
    
    def record_healing_event(
        self,
        element_name: str,
        original_strategy: LocatorStrategy,
        healed_strategy: LocatorStrategy,
        healing_method: str,
        success: bool
    ) -> None:
        """Record a healing event when a locator was healed."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO healing_events
                (element_name, original_strategy, healed_strategy, healing_method, success)
                VALUES (?, ?, ?, ?, ?)
            """, (
                element_name,
                json.dumps(original_strategy.to_dict()),
                json.dumps(healed_strategy.to_dict()),
                healing_method,
                success
            ))
            
            conn.commit()
            
            logger.info(
                f"Healing event recorded: {element_name} | "
                f"Original: {original_strategy.type}={original_strategy.value} | "
                f"Healed: {healed_strategy.type}={healed_strategy.value} | "
                f"Method: {healing_method} | Success: {success}"
            )
    
    def get_reliability_score(self, strategy: LocatorStrategy) -> float:
        """Get current reliability score for a strategy."""
        strategy_hash = self._get_strategy_hash(strategy)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT reliability_score FROM reliability_scores
                WHERE strategy_hash = ?
            """, (strategy_hash,))
            
            row = cursor.fetchone()
            return row[0] if row else 0.5
    
    def get_best_strategies_for_element(
        self,
        element_name: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get best-performing strategies for an element based on history."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT strategy_type, strategy_value, reliability_score, 
                       success_count, failure_count
                FROM reliability_scores
                WHERE element_name = ?
                ORDER BY reliability_score DESC, success_count DESC
                LIMIT ?
            """, (element_name, limit))
            
            return [
                {
                    "type": row[0],
                    "value": row[1],
                    "reliability": row[2],
                    "success_count": row[3],
                    "failure_count": row[4]
                }
                for row in cursor.fetchall()
            ]


class SelfHealingDriver:
    """Wrapper around Appium driver with self-healing capabilities."""
    
    def __init__(
        self,
        driver: Any,
        config: Optional[Dict[str, Any]] = None,
        repository: Optional[HealingRepository] = None
    ):
        """Initialize self-healing driver.
        
        Args:
            driver: Appium WebDriver instance
            config: Configuration dictionary with healing settings
            repository: HealingRepository instance for storing learning data
        """
        self.driver = driver
        self.config = config or {}
        self.repository = repository or HealingRepository()
        
        self.max_retries = self.config.get("max_retries", 3)
        self.ai_vision_enabled = self.config.get("ai_vision_healing", False)
        self.wait_timeout = self.config.get("explicit_wait_timeout", 10)
        self.primary_strategy_timeout = float(self.config.get("primary_strategy_timeout", min(self.wait_timeout, 4)))
        self.fallback_strategy_timeout = float(self.config.get("fallback_strategy_timeout", 1.5))
        
        if WebDriverWait:
            self.wait = WebDriverWait(self.driver, self.wait_timeout)
        else:
            self.wait = None
    
    def find_element(
        self,
        locator_strategies: List[LocatorStrategy],
        screen_name: str = ""
    ) -> WebElement:
        """Find element using multiple strategies with automatic fallback.
        
        Args:
            locator_strategies: List of LocatorStrategy objects in priority order
            screen_name: Name of current screen (for logging/analytics)
        
        Returns:
            WebElement if found
        
        Raises:
            NoSuchElementException: If all strategies fail and healing fails
        """
        if not locator_strategies:
            raise ValueError("At least one locator strategy required")
        
        # Sort strategies by priority and reliability
        sorted_strategies = sorted(
            locator_strategies,
            key=lambda s: (s.priority, -self.repository.get_reliability_score(s))
        )
        
        element_name = sorted_strategies[0].element_name
        last_exception = None
        
        for index, strategy in enumerate(sorted_strategies):
            try:
                start_time = time.time()
                locator = self._build_locator(strategy.type, strategy.value)

                # Keep first strategy reasonably patient, but make fallbacks fast
                # to avoid long no-action stalls on emulator.
                if WebDriverWait and EC:
                    timeout = self.primary_strategy_timeout if index == 0 else self.fallback_strategy_timeout
                    if timeout > 0:
                        element = WebDriverWait(self.driver, timeout).until(
                            EC.presence_of_element_located(locator)
                        )
                    else:
                        element = self.driver.find_element(*locator)
                else:
                    element = self.driver.find_element(*locator)
                
                execution_time = int((time.time() - start_time) * 1000)
                
                # Record success
                self.repository.record_attempt(strategy, True, execution_time, screen_name)
                
                logger.info(
                    f"✓ Found element '{element_name}' using {strategy.type}={strategy.value} "
                    f"({execution_time}ms)"
                )
                
                return element
                
            except (NoSuchElementException, TimeoutException) as e:
                last_exception = e
                execution_time = int((time.time() - start_time) * 1000)
                
                # Record failure
                self.repository.record_attempt(strategy, False, execution_time, screen_name)
                
                logger.warning(
                    f"✗ Failed to find element '{element_name}' using "
                    f"{strategy.type}={strategy.value}"
                )
                continue
        
        # All strategies failed - attempt healing
        logger.warning(f"All locators failed for '{element_name}'. Attempting self-healing...")
        
        if self.ai_vision_enabled:
            healed_element = self._ai_heal_and_locate(sorted_strategies, screen_name)
            if healed_element:
                return healed_element
        
        # Healing failed - raise exception
        raise NoSuchElementException(
            f"Failed to locate element '{element_name}' after trying {len(sorted_strategies)} "
            f"strategies and healing attempts"
        ) from last_exception
    
    def _build_locator(self, strategy_type: str, value: str) -> Tuple[str, str]:
        """Convert strategy to Appium locator tuple."""
        if not AppiumBy:
            raise ImportError("Appium not installed")

        def _escape_uiautomator(text: str) -> str:
            return text.replace('\\', '\\\\').replace('"', '\\"')

        strategy_type = (strategy_type or "text").strip().lower()
        value = str(value or "").strip()
        
        if strategy_type == "resource_id" or strategy_type == "id":
            return (AppiumBy.ID, value)
        
        if strategy_type == "accessibility_id" or strategy_type == "content_desc":
            return (AppiumBy.ACCESSIBILITY_ID, value)
        
        if strategy_type == "xpath":
            return (AppiumBy.XPATH, value)
        
        if strategy_type == "class_name":
            return (AppiumBy.CLASS_NAME, value)

        if strategy_type == "class_text":
            # Expected format: "<class>:<text>" (e.g. android.widget.Button:Login)
            if ":" in value:
                class_name, text_value = value.split(":", 1)
                class_name = _escape_uiautomator(class_name.strip())
                text_value = _escape_uiautomator(text_value.strip())
                selector = (
                    f'new UiSelector().className("{class_name}")'
                    f'.textContains("{text_value}")'
                )
                return (AppiumBy.ANDROID_UIAUTOMATOR, selector)
            selector = f'new UiSelector().className("{_escape_uiautomator(value)}")'
            return (AppiumBy.ANDROID_UIAUTOMATOR, selector)
        
        if strategy_type == "text":
            # Use contains for faster, more forgiving matching across UI variants.
            escaped = _escape_uiautomator(value)
            selector = f'new UiSelector().textContains("{escaped}")'
            return (AppiumBy.ANDROID_UIAUTOMATOR, selector)

        if strategy_type == "text_contains":
            selector = f'new UiSelector().textContains("{_escape_uiautomator(value)}")'
            return (AppiumBy.ANDROID_UIAUTOMATOR, selector)
        
        # Default to text-based UiAutomator2 selector
        selector = f'new UiSelector().textContains("{_escape_uiautomator(value)}")'
        return (AppiumBy.ANDROID_UIAUTOMATOR, selector)
    
    def _ai_heal_and_locate(
        self,
        failed_strategies: List[LocatorStrategy],
        screen_name: str
    ) -> Optional[WebElement]:
        """Attempt to heal locator using AI vision (placeholder).
        
        This is a placeholder for AI vision-based healing.
        In production, this would:
        1. Take a screenshot
        2. Send to vision LLM with element description
        3. Get new locator suggestions
        4. Try new locators
        5. Store successful healing for future use
        """
        logger.info("AI vision healing not yet implemented - placeholder")
        
        # TODO: Implement AI vision healing
        # 1. screenshot = self.driver.get_screenshot_as_base64()
        # 2. Call vision LLM with screenshot and element description
        # 3. Parse response for new locator suggestions
        # 4. Try new suggestions and record results
        
        return None
    
    def tap_element(
        self,
        locator_strategies: List[LocatorStrategy],
        screen_name: str = ""
    ) -> None:
        """Find and tap an element with self-healing."""
        element = self.find_element(locator_strategies, screen_name)
        element.click()
        logger.info(f"Tapped element: {locator_strategies[0].element_name}")
    
    def type_text(
        self,
        locator_strategies: List[LocatorStrategy],
        text: str,
        screen_name: str = ""
    ) -> None:
        """Find element and type text with self-healing."""
        element = self.find_element(locator_strategies, screen_name)
        element.clear()
        element.send_keys(text)
        logger.info(f"Typed text into: {locator_strategies[0].element_name}")
