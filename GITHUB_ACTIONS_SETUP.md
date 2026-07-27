# 🚀 GitHub Actions Setup Guide

## Latest Notes (Jul 2026)

- Runtime hardening updates were delivered in live demo/backend logic (env scoping, realtime timeout, async stale-run watchdog, concise user-facing failures).
- Self-healing result visibility was added in live demo UI for easier post-run verification.
- Report-serving compatibility was hardened so both legacy and normalized artifact URL styles resolve correctly during manual demo checks.
- Live demo flow selection now refreshes to a clean run state (`/?flow_type=...`) to prevent stale previous-run result views.
- Live demo now clears previous result sections immediately on flow switch/new run submit, so stale report/screenshot panels are not shown while the current run is in progress.
- Cross-app runtime toggles were added to `.env.example` for easier profile control:
  - `ENABLE_APP_SPECIFIC_LOCATOR_HINTS`
  - `ENABLE_APP_SPECIFIC_NAVIGATION`
- Screenshot pipeline generation is now profile-aware:
  - reference demo profile keeps self-healing generation,
  - non-reference profiles use generic generator defaults.
- When validating after pull from `main`, include at least one deterministic realtime check:

```powershell
python -m pytest tests/test_realtime_e2e_flow.py -q
```

## ✅ **Prerequisites Verified**

- ✅ LiteLLM Gateway connection working locally
- ✅ API Key: `sk-PZOYiIou9n7y5FeKcvv5dw`
- ✅ Endpoint: `http://107.22.98.31:10501/v1`
- ✅ Model: `Azure#gpt-5.4`
- ✅ Workflow updated to trigger on `Aditya` branch

---

## 📋 **Step-by-Step GitHub Actions Configuration**

### **Step 1: Add GitHub Secrets**

GitHub Secrets keep your API keys secure and encrypted.

#### **A. Navigate to Repository Settings**

1. Go to: `https://github.com/PriyankaPattewar/Project13_Captstone`
2. Click **Settings** (top right)
3. In left sidebar, click **Secrets and variables** → **Actions**

#### **B. Add Repository Secret**

Click **New repository secret** and add:

**Secret 1: LiteLLM API Key**
- **Name**: `LITELLM_API_KEY`
- **Value**: `sk-PZOYiIou9n7y5FeKcvv5dw`
- Click **Add secret**

![GitHub Secrets Screenshot](https://docs.github.com/assets/cb-45848/mw-1440/images/help/repository/actions-secrets-add.webp)

---

### **Step 2: Add Repository Variable (Optional)**

Variables control workflow behavior.

#### **Navigate to Variables**

1. Still in **Settings** → **Secrets and variables** → **Actions**
2. Click the **Variables** tab (next to Secrets)
3. Click **New repository variable**

#### **Add Variable**

**Variable 1: Enable LiteLLM Testing**
- **Name**: `LITELLM_ENABLED`
- **Value**: `true`
- Click **Add variable**

> **Note**: This controls whether the LiteLLM gateway test runs in CI/CD. Set to `false` to disable.

---

### **Step 3: Verify Workflow File**

The workflow is already configured to trigger on your `Aditya` branch.

**Triggers on:**
- ✅ Push to `Aditya` branch
- ✅ Push to `main` or `develop` branches
- ✅ Pull requests to these branches
- ✅ Manual workflow dispatch

**Workflow includes:**
1. Code quality checks (Black, Flake8)
2. Unit tests with coverage
3. Security scanning (Bandit, Safety)
4. Mock integration tests
5. **LiteLLM Gateway test** (if secrets configured)
6. Build & package
7. Cost analysis report

---

### **Step 4: Push to GitHub**

Now commit and push your changes to trigger the workflow.

#### **Option A: Push Current Changes**

```powershell
# Check current status
git status

# Add all new files
git add .

# Commit with message
git commit -m "feat: Add LangChain, self-healing, and LiteLLM gateway support"

# Push to Aditya branch
git push origin Aditya
```

#### **Option B: If You Need to Pull First**

```powershell
# Pull latest changes from Aditya branch
git pull origin Aditya

# Add your changes
git add .

# Commit
git commit -m "feat: Add LangChain, self-healing, and LiteLLM gateway support"

# Push
git push origin Aditya
```

---

### **Step 5: Monitor Workflow Execution**

#### **A. View Workflow Run**

1. Go to: `https://github.com/PriyankaPattewar/Project13_Captstone/actions`
2. You'll see your workflow run starting
3. Click on the run to see details

#### **B. Check Job Status**

You'll see these jobs running:

- ✅ **Code Quality Checks** - Linting and formatting
- ✅ **Run Tests** - Unit tests with coverage
- ✅ **Security Scan** - Dependency and code security
- ✅ **Integration Test** - Mock pipeline test
- ✅ **LiteLLM Gateway Test** - Real gateway connection (if enabled)
- ✅ **Build Package** - Create distributable package
- ✅ **Cost Analysis** - Token usage report

#### **C. View LiteLLM Gateway Test**

Click on **LiteLLM Gateway Connection Test** job to see:

```
Testing LiteLLM Gateway Connection
============================================================
API Base: http://107.22.98.31:10501/v1
Model: Azure#gpt-5.4
============================================================
✅ SUCCESS!
Model: Azure#gpt-5.4
Response: Hello! How can I help you
============================================================
```

---

## 🔒 **Security Best Practices**

### **What's Protected:**

✅ **API Key never appears in logs** - GitHub automatically redacts secret values
✅ **Secrets encrypted at rest** - GitHub encrypts all secrets
✅ **Secrets only available to workflows** - Not visible in code or PRs
✅ **`.env` file in .gitignore** - Local credentials never committed

### **What You Should Never Do:**

❌ Don't commit `.env` file to GitHub
❌ Don't hardcode API keys in code
❌ Don't print secrets in logs
❌ Don't share secret values in PR comments

---

## 🧪 **Testing the Workflow**

### **Test 1: Manual Trigger** (Recommended First)

1. Go to: `https://github.com/PriyankaPattewar/Project13_Captstone/actions`
2. Click on **Mobile Test Generator CI/CD** workflow
3. Click **Run workflow** button
4. Select branch: **Aditya**
5. Click **Run workflow**

This tests the workflow without needing to push code.

### **Test 2: Push Trigger**

```powershell
# Make a small change
echo "# Test commit" >> README.md

# Commit and push
git add README.md
git commit -m "test: Trigger GitHub Actions"
git push origin Aditya
```

### **Test 3: Verify LiteLLM Job**

Check if the LiteLLM gateway test runs:

1. Go to Actions tab
2. Click on your workflow run
3. Look for **LiteLLM Gateway Connection Test** job
4. Verify it shows ✅ SUCCESS

---

## 📊 **Workflow Configuration Details**

## Deterministic Realtime Flow Validation (Latest)

In addition to pipeline/integration checks, you can run the strict realtime emulator flow as a targeted validation:

```powershell
python -m pytest tests/test_realtime_e2e_flow.py -q
```

Recommended usage:

1. Use full pipeline tests when validating screenshot-driven generation behavior.
2. Use deterministic flow test when validating fixed business journey stability on emulator.
3. Run both before release if live demo exposes both options.

### **Jobs That Always Run:**

1. **Code Quality** - Checks formatting and linting
2. **Tests** - Unit and integration tests
3. **Security** - Scans for vulnerabilities
4. **Build** - Creates package

### **Jobs That Run Conditionally:**

5. **LiteLLM Gateway Test**
   - Only runs if `LITELLM_ENABLED=true` variable is set
   - Only runs on push (not pull requests)
   - Tests real gateway connection

### **Environment Variables in Workflow:**

```yaml
VISION_AGENT_PROVIDER=openai
TESTCASE_AGENT_PROVIDER=openai
OPENAI_API_KEY=${{ secrets.LITELLM_API_KEY }}
OPENAI_MODEL=Azure#gpt-5.4
OPENAI_API_BASE=http://107.22.98.31:10501/v1
```

---

## 🔧 **Troubleshooting**

### **Issue 1: Secret Not Found**

**Error:**
```
Error: Secret LITELLM_API_KEY not found
```

**Solution:**
- Go to Settings → Secrets → Actions
- Verify secret name is exactly: `LITELLM_API_KEY` (case-sensitive)
- Re-add the secret if needed

---

### **Issue 2: LiteLLM Job Doesn't Run**

**Possible Causes:**

1. **Variable not set**: Add `LITELLM_ENABLED=true` variable
2. **Pull request**: LiteLLM job skips PRs for security
3. **Wrong branch**: Ensure pushing to `Aditya`, `main`, or `develop`

**Check:**
```yaml
if: github.event_name != 'pull_request' && vars.LITELLM_ENABLED == 'true'
```

---

### **Issue 3: Gateway Connection Fails in CI**

**Error:**
```
❌ FAILED!
Error: Connection timeout
```

**Possible Causes:**

1. **Gateway not accessible from GitHub**: Your gateway `http://107.22.98.31:10501` might be behind a firewall
2. **Internal network only**: Gateway may only be accessible from your local network

**Solutions:**

**Option A: Use Mock Provider for CI** (Recommended)
```yaml
# In workflow, use mock for CI
VISION_AGENT_PROVIDER=mock
TESTCASE_AGENT_PROVIDER=mock
```

**Option B: Expose Gateway Publicly**
- Work with your IT team to expose the gateway
- Use a public IP or domain
- Add authentication/rate limiting

**Option C: Self-Hosted Runner**
- Set up GitHub self-hosted runner on your network
- Runner can access internal gateway

---

### **Issue 4: Workflow Not Triggering**

**Checklist:**

- ✅ Workflow file is in `.github/workflows/` directory
- ✅ File has `.yml` or `.yaml` extension
- ✅ YAML syntax is valid (check indentation)
- ✅ Pushing to correct branch (`Aditya`)
- ✅ Workflow file is committed and pushed

**Verify:**
```powershell
# Check if workflow file exists in repo
git ls-files .github/workflows/
```

---

## 📝 **Summary Checklist**

Before pushing to GitHub, verify:

- [ ] Secrets added to GitHub repository
  - [ ] `LITELLM_API_KEY` secret created
- [ ] Variables configured (optional)
  - [ ] `LITELLM_ENABLED=true` variable added
- [ ] All local changes committed
- [ ] `.env` file NOT committed (in .gitignore)
- [ ] Workflow file updated for `Aditya` branch
- [ ] Ready to push to GitHub

---

## 🚀 **Ready to Deploy?**

Run these commands:

```powershell
# 1. Check status
git status

# 2. Add all changes
git add .

# 3. Commit
git commit -m "feat: Add LangChain, self-healing, and LiteLLM gateway support

- Added LangChain integration for robust LLM handling
- Implemented self-healing test framework
- Configured LiteLLM gateway support
- Updated GitHub Actions for Aditya branch
- Added comprehensive testing and documentation"

# 4. Push to trigger workflow
git push origin Aditya
```

# 5. Monitor at:
Visit: `https://github.com/PriyankaPattewar/Project13_Captstone/actions`

---

## 🆘 **Need Help?**

### **Common Questions**

**Q: Will the API key be visible in logs?**
A: No, GitHub automatically redacts secret values from logs.

**Q: Can I test locally before pushing?**
A: Yes! You already did - `python utils/custom_gateway.py` ✅

**Q: What if gateway is not accessible from GitHub?**
A: Use mock provider for CI, or set up self-hosted runner.

**Q: How do I disable LiteLLM test in CI?**
A: Set `LITELLM_ENABLED` variable to `false` or remove the variable.

---

## 📞 **Contact Info**

**Repository**: https://github.com/PriyankaPattewar/Project13_Captstone
**Branch**: Aditya
**Workflow**: Mobile Test Generator CI/CD

---

**Ready to push? Follow the commands above!** 🚀
