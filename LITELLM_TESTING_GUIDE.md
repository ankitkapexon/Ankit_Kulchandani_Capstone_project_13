# 🚀 LiteLLM Gateway - Local Testing Guide

## ✅ **Configuration Complete**

Your project is now configured to use the **LiteLLM Gateway** at `http://107.22.98.31:10501`

---

## 📋 **What Was Configured**

### **1. Environment File Created**
✅ [.env](.env) - Configured with your LiteLLM gateway credentials
- **API Key**: `sk-PZOYiIou9n7y5FeKcvv5dw`
- **Endpoint**: `http://107.22.98.31:10501/v1`
- **Model**: `Azure#gpt-5.4`

### **2. Custom Gateway Client Created**
✅ [utils/custom_gateway.py](utils/custom_gateway.py) - Handles LiteLLM-specific authentication
- Supports `x-litellm-api-key` header if needed
- Falls back to standard OpenAI client format
- Includes connection testing utility

### **3. Updated Components**
✅ [.env.example](.env.example) - Added LiteLLM configuration examples
✅ [agents/langchain_vision_agent.py](agents/langchain_vision_agent.py) - LiteLLM gateway detection
✅ [utils/__init__.py](utils/__init__.py) - Exported gateway utilities

---

## 🧪 **Step-by-Step Testing**

### **Test 1: Configuration Loading** ✅

```powershell
# Verify configuration is loaded correctly
python -c "from services.enhanced_config import get_config; c = get_config(); print(f'✅ API Base: {c.openai_api_base}'); print(f'✅ Model: {c.openai_model}'); print(f'✅ Key: {c.openai_api_key[:15]}...')"
```

**Expected Output:**
```
✅ API Base: http://107.22.98.31:10501/v1
✅ Model: Azure#gpt-5.4
✅ Key: sk-PZOYiIou9n7...
```

---

### **Test 2: Gateway Connection** 🔌

```powershell
# Test direct connection to LiteLLM gateway
python utils/custom_gateway.py
```

**What this does:**
1. Creates OpenAI client with your gateway URL
2. Sends a simple "Hello" message
3. Verifies the response

**Expected Output:**
```
============================================================
Testing LiteLLM Gateway Connection
============================================================
API Base: http://107.22.98.31:10501/v1
Model: Azure#gpt-5.4
============================================================
✅ SUCCESS!
Model: Azure#gpt-5.4
Response: Hello! How can I assist you today?
============================================================
```

**If it fails**, you'll see:
```
❌ FAILED!
Error: [error details]
```

---

### **Test 3: LangChain Integration** 🔗

```powershell
# Test LangChain with LiteLLM gateway
python -c "
from agents.langchain_vision_agent import LangChainVisionAgent
agent = LangChainVisionAgent()
print('✅ LangChain agent created successfully')
print(f'✅ Using model: {agent.model_name}')
print(f'✅ API endpoint: {agent.api_base}')
"
```

**Expected Output:**
```
✅ LangChain agent created successfully
✅ Using model: Azure#gpt-5.4
✅ API endpoint: http://107.22.98.31:10501/v1
```

---

### **Test 4: Vision Analysis (Requires Screenshot)** 📸

```powershell
# Test screenshot analysis with LiteLLM gateway
# First, ensure you have a screenshot in input folder
python -c "
from agents.langchain_vision_agent import create_langchain_vision_agent
from pathlib import Path

# Create agent
agent = create_langchain_vision_agent(provider='openai')

# Find a test screenshot
screenshots = list(Path('artifacts/input_screenshots').glob('*.png'))
if screenshots:
    print(f'Testing with: {screenshots[0].name}')
    result = agent.analyze_image(str(screenshots[0]))
    print(f'✅ Analysis complete!')
    print(f'Screen: {result.get(\"screen_name\")}')
    print(f'Elements found: {len(result.get(\"elements\", []))}')
else:
    print('⚠️ No screenshots found in artifacts/input_screenshots/')
    print('Add a screenshot to test vision analysis')
"
```

---

## 🔧 **Troubleshooting**

### **Issue 1: Connection Timeout**
```
Error: Connection timeout
```

**Solutions:**
- ✅ Check if gateway is accessible: `curl http://107.22.98.31:10501/docs`
- ✅ Verify you're not behind a firewall/VPN that blocks the gateway
- ✅ Check if gateway is running

---

### **Issue 2: Authentication Failed**
```
Error: 401 Unauthorized
```

**Solutions:**
- ✅ Verify API key is correct in [.env](.env)
- ✅ Check if gateway requires `x-litellm-api-key` header
- ✅ Try adding custom header in `.env`:
  ```env
  CUSTOM_LLM_HEADERS=x-litellm-api-key
  ```

---

### **Issue 3: Model Not Found**
```
Error: Model 'Azure#gpt-5.4' not found
```

**Solutions:**
- ✅ Verify model name format with gateway admin
- ✅ Try alternative format: `OPENAI_MODEL=gpt-5.4`
- ✅ Check available models: `curl http://107.22.98.31:10501/v1/models`

---

### **Issue 4: Temperature Error**
```
Error: UnsupportedParamsError - temperature not supported
```

**Solution - Already handled in code:**
The LangChain agent automatically handles this and retries without temperature parameter.

---

## 📊 **Verifying Gateway Features**

### **Check Vision Support**

```powershell
# Check if your model supports vision/multimodal
python -c "
import requests
response = requests.get('http://107.22.98.31:10501/v1/models')
print('Available models:', response.json())
"
```

Look for models with "vision" or "gpt-4" in the name.

---

### **Check Token Usage**

After running any test, check:
```powershell
cat artifacts/token_usage.log
```

You should see:
```
2026-07-20 15:30:15 | Vision Analysis | Azure#gpt-5.4 | 1,250 tokens | $0.0015
```

---

## ✅ **Next Steps**

### **If All Tests Pass:**

1. **Run Full Pipeline**
   ```powershell
   python pipelines/run_all_enhanced.py artifacts/input_screenshots
   ```

2. **Monitor Token Usage**
   ```powershell
   # Check cost tracking
   cat artifacts/token_usage.log
   ```

3. **View Generated Scripts**
   ```powershell
   ls artifacts/generated_appium_scripts/
   ```

---

### **If Tests Fail:**

1. **Contact Gateway Administrator**
   - Verify API key is active
   - Confirm model name format
   - Check if special headers are needed
   - Verify gateway is running and accessible

2. **Try Standard OpenAI (Fallback)**
   ```powershell
   # Edit .env and switch to standard OpenAI temporarily
   # OPENAI_API_BASE=https://api.openai.com/v1
   # OPENAI_MODEL=gpt-4o-mini
   ```

---

## 📝 **Configuration Reference**

### **Current Settings in .env**

```env
VISION_AGENT_PROVIDER=openai
TESTCASE_AGENT_PROVIDER=openai
OPENAI_API_KEY=sk-PZOYiIou9n7y5FeKcvv5dw
OPENAI_MODEL=Azure#gpt-5.4
OPENAI_API_BASE=http://107.22.98.31:10501/v1
```

### **Optional Adjustments**

**Temperature (if needed):**
Add to `.env`:
```env
LLM_TEMPERATURE=1
```

Then update `agents/langchain_vision_agent.py` line 86 to use config value.

**Custom Headers (if standard auth fails):**
```env
CUSTOM_LLM_HEADERS=x-litellm-api-key
```

---

## 🎯 **Success Criteria**

✅ **Test 1**: Configuration loads without errors  
✅ **Test 2**: Gateway returns successful response  
✅ **Test 3**: LangChain agent initializes  
✅ **Test 4**: Screenshot analysis works (if vision supported)  

**Once all pass, you're ready for GitHub Actions setup!**

---

## 🆘 **Getting Help**

1. **Check Gateway Documentation**
   - Visit: `http://107.22.98.31:10501/docs`
   - Look for authentication requirements

2. **Review Error Logs**
   ```powershell
   # Check Python errors
   python utils/custom_gateway.py 2>&1 | Select-String "Error"
   ```

3. **Test with curl**
   ```powershell
   curl -X POST http://107.22.98.31:10501/v1/chat/completions `
     -H "Content-Type: application/json" `
     -H "Authorization: Bearer sk-PZOYiIou9n7y5FeKcvv5dw" `
     -d '{"model":"Azure#gpt-5.4","messages":[{"role":"user","content":"test"}]}'
   ```

---

## 📞 **Contact Info**

**Gateway**: http://107.22.98.31:10501  
**Docs**: http://107.22.98.31:10501/docs  
**Model**: Azure#gpt-5.4  

---

**Ready to test?** Start with Test 1 above! 🚀
