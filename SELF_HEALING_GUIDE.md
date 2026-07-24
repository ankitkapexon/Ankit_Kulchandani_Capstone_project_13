# 🚀 Self-Healing & LangChain Implementation Guide

This guide explains how to use the enhanced mobile test automation framework with **self-healing capabilities** and **LangChain integration**.

---

## 📋 **What's New**

### ✅ **P0 Fixes Implemented**
1. ✅ **Fixed hardcoded paths** - Now uses centralized configuration
2. ✅ **Fixed logger import bug** - Proper `logging` module import in generated scripts
3. ✅ **Added .env.example** - Complete environment configuration template

### 🎯 **Major Features Added**
1. ✅ **LangChain Integration** - Structured output, automatic retry, token tracking
2. ✅ **Self-Healing Tests** - Multi-strategy locators with automatic fallback
3. ✅ **Centralized Config** - Type-safe configuration management
4. ✅ **CI/CD Pipeline** - GitHub Actions workflow for automated testing

---

## 🛠️ **Setup Instructions**

### **Step 1: Install Enhanced Dependencies**

```powershell
# Update dependencies (includes LangChain, self-healing tools)
pip install -r requirements.txt
```

**New dependencies include:**
- `langchain` & `langchain-openai` - LLM orchestration
- `Pillow` & `imagehash` - Visual self-healing (future)
- `faiss-cpu` - Vector similarity search for RAG
- `diskcache` - LLM response caching

### **Step 2: Configure Environment**

```powershell
# Copy the example environment file
Copy-Item .env.example .env

# Edit .env with your actual values
notepad .env
```

**Required configuration:**
```env
# AI Providers
VISION_AGENT_PROVIDER=openai
TESTCASE_AGENT_PROVIDER=openai
OPENAI_API_KEY=your_actual_api_key_here

# Self-Healing Settings
SELF_HEALING_ENABLED=true
HEALING_MAX_RETRIES=3
AI_VISION_HEALING=true

# App Configuration (update path to your APK)
APP_PATH=demo_mobile_apps/mda-2.2.0-25.apk
```

### **Step 3: Verify Configuration**

```powershell
# Test configuration loading
python -c "from services.enhanced_config import get_config; config = get_config(); print(f'✓ Config loaded: {config.openai_model}')"
```

---

## 🎯 **Usage Guide**

### **Option 1: Full Pipeline with Self-Healing (Recommended)**

```powershell
# Run enhanced pipeline with LangChain + self-healing
python pipelines/run_all_enhanced.py artifacts/input_screenshots
```

This runs:
1. **LangChain Vision Agent** → SSM JSON (with token tracking)
2. **LangChain Test Case Agent** → Manual test cases
3. **Multi-Strategy Locator Agent** → Locators with fallbacks
4. **Self-Healing Script Generator** → Pytest scripts
5. **Reviewer Agent** → Code review
6. **Reporter Agent** → HTML test execution report

### **Option 2: Run Individual Enhanced Components**

#### **A. Generate SSM with LangChain**
```powershell
# Uses LangChain for structured output and auto-retry
python pipelines/ssm_generator.py artifacts/input_screenshots --use-langchain
```

**Benefits:**
- Automatic retry on parse errors
- Structured Pydantic output validation
- Token usage tracking
- LLM response caching

#### **B. Generate Multi-Strategy Locators**
```powershell
# Creates locators with 3-6 fallback strategies per element
python -c "from agents.multi_strategy_locator_agent import MultiStrategyLocatorAgent; agent = MultiStrategyLocatorAgent(); agent.run()"
```

**Output:** Each element gets multiple strategies:
```json
{
  "element": "Login Button",
  "primary_strategy": {
    "type": "resource_id",
    "value": "com.app:id/loginBtn",
    "priority": 1,
    "reliability": 0.95
  },
  "fallback_strategies": [
    {
      "type": "accessibility_id",
      "value": "Login",
      "priority": 2,
      "reliability": 0.90
    },
    {
      "type": "text",
      "value": "Login",
      "priority": 4,
      "reliability": 0.75
    }
  ]
}
```

#### **C. Generate Self-Healing Test Scripts**
```powershell
# Creates tests that automatically try fallback locators
python -c "from agents.self_healing_appium_generator import SelfHealingAppiumGenerator; gen = SelfHealingAppiumGenerator(); gen.generate_scripts_from_directory()"
```

**Generated scripts include:**
- Multi-strategy locator support
- Automatic fallback on failure
- Healing event logging to SQLite
- Proper configuration management
- Fixed logger imports

---

## 🔍 **Self-Healing in Action**

### **How It Works**

1. **Test tries primary locator** (e.g., resource_id)
   ```python
   strategies = [
       LocatorStrategy("resource_id", "com.app:id/loginBtn", priority=1),
       LocatorStrategy("accessibility_id", "Login", priority=2),
       LocatorStrategy("text", "Login", priority=4)
   ]
   healing_driver.tap_element(strategies, screen_name="Login")
   ```

2. **If primary fails** → Automatically tries fallback #1
3. **If all fail** → Triggers AI vision healing (future)
4. **Success tracked** → Reliability scores updated in database

### **Healing Repository**

All attempts are logged to `artifacts/healing_repository.db`:

```sql
-- View element reliability scores
SELECT element_name, strategy_type, reliability_score, success_count, failure_count
FROM reliability_scores
ORDER BY reliability_score DESC;

-- View healing events
SELECT * FROM healing_events
WHERE success = 1
ORDER BY timestamp DESC;
```

### **Analyzing Healing Data**

```python
from utils.self_healing import HealingRepository

repo = HealingRepository()

# Get best strategies for an element
best = repo.get_best_strategies_for_element("Login Button")
print(f"Best locator: {best[0]['type']} (reliability: {best[0]['reliability']})")
```

---

## 💰 **Token Usage & Cost Tracking**

### **View Token Usage**

```python
from agents.langchain_vision_agent import LangChainVisionAgent

agent = LangChainVisionAgent()
agent.analyze_image("screenshots/login.png")

# Get usage stats
stats = agent.get_usage_stats()
print(f"Tokens used: {stats['total_tokens']}")
print(f"Cost: ${stats['total_cost']:.4f}")
```

### **Cost Tracking Log**

Check `artifacts/token_usage.log` for detailed tracking:
```
2026-07-20 14:30:15 | Vision Analysis | gpt-4o-mini | 1,250 tokens | $0.0015
2026-07-20 14:30:45 | Test Generation | gpt-4o-mini | 2,100 tokens | $0.0025
```

---

## 🧪 **Running Self-Healing Tests**

### **Run Generated Tests**

```powershell
# Execute self-healing tests (requires Appium server running)
python pipelines/reporter.py
```

**What happens:**
- Tests use `SelfHealingDriver` automatically
- Failed locators trigger fallback strategies
- All attempts logged to healing repository
- HTML report shows test results

### **Check Healing Effectiveness**

```powershell
# View healing statistics
python -c "
from utils.self_healing import HealingRepository
repo = HealingRepository()
import sqlite3
conn = sqlite3.connect('artifacts/healing_repository.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) as total, SUM(success) as successes FROM locator_attempts')
row = cursor.fetchone()
print(f'Total attempts: {row[0]}, Success rate: {row[1]/row[0]*100:.1f}%')
"
```

---

## 📊 **CI/CD Integration**

### **GitHub Actions Workflow**

The pipeline is configured in `.github/workflows/ci.yml`:

**Workflow includes:**
- ✅ Code quality checks (Black, Flake8, isort)
- ✅ Unit & integration tests with coverage
- ✅ Security scanning (Bandit, Safety)
- ✅ Mock pipeline integration test
- ✅ Build & package artifacts
- ✅ Cost analysis reports

### **Trigger Workflow**

```bash
# Push to trigger CI
git add .
git commit -m "feat: Add self-healing tests"
git push origin main
```

---

## 🎓 **Best Practices**

### **1. Locator Strategy Priority**

Always order strategies by stability:
```python
1. resource_id      # Most stable (95% reliability)
2. accessibility_id # Very stable (90%)
3. content_desc     # Stable (85%)
4. text             # Moderate (75%)
5. class_text       # Lower (70%)
6. xpath            # Least stable (60%)
```

### **2. Regular Healing Repository Analysis**

```powershell
# Weekly: Review failing locators
python -c "
from utils.self_healing import HealingRepository
repo = HealingRepository()
import sqlite3
conn = sqlite3.connect('artifacts/healing_repository.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT element_name, strategy_type, failure_count, reliability_score
    FROM reliability_scores
    WHERE reliability_score < 0.7
    ORDER BY failure_count DESC
    LIMIT 10
''')
print('Top 10 problematic locators:')
for row in cursor.fetchall():
    print(f'  - {row[0]}: {row[1]} (failures: {row[2]}, score: {row[3]:.2f})')
"
```

### **3. Enable LLM Caching for Cost Savings**

```env
# In .env file
ENABLE_LLM_CACHE=true
CACHE_BACKEND=file
CACHE_TTL=86400  # 24 hours
```

**Savings:** Repeated screenshot analysis uses cached results (free!).

---

## 🔧 **Troubleshooting**

### **Issue: "LangChain not installed"**
```powershell
pip install langchain langchain-openai
```

### **Issue: "Healing repository database locked"**
```powershell
# Close any open connections and retry
rm artifacts/healing_repository.db
# Database will be recreated on next run
```

### **Issue: "All locators failed"**
1. Check Appium server is running
2. Verify app package/activity in .env
3. Review healing repository for patterns:
   ```powershell
   python -c "from utils.self_healing import HealingRepository; repo = HealingRepository(); print(repo.get_best_strategies_for_element('Login Button'))"
   ```

---

## 📈 **Metrics & Reporting**

### **Self-Healing Effectiveness**

Track over time:
- **Primary Success Rate**: % of times primary locator works
- **Healing Success Rate**: % of times fallback saves the test
- **Average Fallback Depth**: How many strategies needed on average

### **Cost Metrics**

Monitor:
- **Token usage per screen**
- **Cost per test generation**
- **Cache hit rate** (when caching enabled)

---

## 🚀 **Next Steps**

1. **Run your first self-healing test generation**:
   ```powershell
   python -c "from agents.multi_strategy_locator_agent import MultiStrategyLocatorAgent; from agents.self_healing_appium_generator import SelfHealingAppiumGenerator; locator_agent = MultiStrategyLocatorAgent(); locator_agent.run(); gen = SelfHealingAppiumGenerator(); gen.generate_scripts_from_directory()"
   ```

2. **Review generated scripts** in `artifacts/generated_appium_scripts/`

3. **Execute tests** and monitor healing events

4. **Analyze results** in healing repository database

5. **Iterate** on locator strategies based on data

---

## 📚 **Additional Resources**

- **LangChain Documentation**: https://python.langchain.com/docs/get_started/introduction
- **Appium Documentation**: https://appium.io/docs/en/latest/
- **Self-Healing Pattern**: See `utils/self_healing.py` for implementation details

---

## 🆘 **Support**

For issues or questions:
1. Check the healing repository logs
2. Review `artifacts/token_usage.log` for LLM costs
3. Examine CI/CD pipeline results in GitHub Actions
4. Open an issue with logs and healing statistics

---

**🎉 You now have a production-ready, self-healing AI test automation framework!**
