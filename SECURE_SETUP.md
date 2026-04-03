# 🔐 PROJECT ATLAS - Secure Credential Setup

## ⚠️ Security Best Practices

**NEVER:**
- ❌ Hardcode credentials in Python files
- ❌ Commit `.env` file to Git
- ❌ Share credentials in messages or chat
- ❌ Log credentials to files
- ❌ Use weak passwords

**ALWAYS:**
- ✅ Use environment variables
- ✅ Use `.env` file (git-ignored)
- ✅ Use strong, unique passwords
- ✅ Rotate credentials regularly
- ✅ Limit API key permissions

---

## Setup Instructions

### Step 1: Create .env File

```bash
# Copy template to actual .env file
cp .env.template .env

# Edit with your credentials
nano .env
# or
code .env
```

### Step 2: Add Your Credentials

Edit `.env` file:

```bash
TRADINGVIEW_EMAIL=puunvasa1996@gmail.com
TRADINGVIEW_PASSWORD=Puunvasa11
```

### Step 3: Load Credentials (Option A: Automatic)

The system uses `python-dotenv` which auto-loads `.env`:

```python
# In Python code (automatically handled):
import os
from dotenv import load_dotenv

load_dotenv()  # Loads .env automatically

email = os.getenv('TRADINGVIEW_EMAIL')
password = os.getenv('TRADINGVIEW_PASSWORD')
```

### Step 4: Load Credentials (Option B: Manual)

If auto-load doesn't work:

```bash
# Load in terminal before running
export $(cat .env | xargs)

# Then run script
python tradingview_scraper.py
```

### Step 5: Verify Setup

```bash
# Check credentials are loaded
echo $TRADINGVIEW_EMAIL
echo $TRADINGVIEW_PASSWORD

# Should show your email and password (hidden in logs)
```

---

## Using the Scripts

### Generate Signals

```bash
# Credentials auto-loaded from .env
python tradingview_strategy_optimizer.py

# Output shows recommended signals
# No credentials exposed in output
```

### Run Live Scraper

```bash
# Credentials auto-loaded from .env
python tradingview_scraper.py

# Monitors TradingView every 5 minutes
# Logs only show status, not credentials
```

### Train Model on Real Data

```bash
# Credentials auto-loaded from .env
python tradingview_model_trainer.py

# Collects real trading data
# Trains model from actual results
```

---

## Environment Variable Locations

### Linux/Mac

**Session-only (expires when terminal closes):**
```bash
export TRADINGVIEW_EMAIL='your_email@example.com'
export TRADINGVIEW_PASSWORD='your_password'
python tradingview_scraper.py
```

**Persistent (add to ~/.bashrc or ~/.zshrc):**
```bash
echo 'export TRADINGVIEW_EMAIL="your_email@example.com"' >> ~/.bashrc
echo 'export TRADINGVIEW_PASSWORD="your_password"' >> ~/.bashrc
source ~/.bashrc
```

**Or use .env file (recommended):**
```bash
# Create .env in project root
TRADINGVIEW_EMAIL=your_email@example.com
TRADINGVIEW_PASSWORD=your_password
```

### Windows

**Command Prompt:**
```cmd
setx TRADINGVIEW_EMAIL "your_email@example.com"
setx TRADINGVIEW_PASSWORD "your_password"
# Restart command prompt
```

**PowerShell:**
```powershell
[Environment]::SetEnvironmentVariable("TRADINGVIEW_EMAIL", "your_email@example.com", "User")
[Environment]::SetEnvironmentVariable("TRADINGVIEW_PASSWORD", "your_password", "User")
```

**Or use .env file:**
```
Create .env in project directory with credentials
```

---

## Checking Credentials Are Hidden

### ✅ Good (Credentials Hidden)

```bash
$ python tradingview_scraper.py
[INFO] Logging in to TradingView...
[INFO] ✅ Successfully logged in
```

Console shows status, not credentials.

### ❌ Bad (Credentials Exposed)

```bash
$ python tradingview_scraper.py
[INFO] Logging in with email: puunvasa1996@gmail.com
[INFO] Using password: Puunvasa11
```

**This would expose your credentials!**

---

## Logs Security

### Check Log Files

```bash
# View logs (check they don't contain credentials)
cat logs/tradingview_scraper.log | grep -i password
# Should return nothing

cat logs/tradingview_scraper.log | grep -i email
# Should return nothing

# Safe to view logs
cat logs/tradingview_scraper.log
```

### Never Log Credentials

```python
# ❌ WRONG - Never do this
logger.info(f"Email: {email}, Password: {password}")

# ✅ CORRECT - Only log status
logger.info("✅ Successfully logged in to TradingView")
```

---

## Git Safety

### Verify .env is Ignored

```bash
# Check .gitignore has .env
grep "^\.env$" .gitignore
# Should show: .env

# Verify .env is not tracked
git status | grep ".env"
# Should show nothing (not listed as untracked)
```

### Before Each Commit

```bash
# Check what's being committed
git status

# If you see .env, STOP and remove it
git rm --cached .env  # Remove from staging

# Add to .gitignore if needed
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Add .env to gitignore"
```

---

## Credential Rotation

### Change Password Periodically

```bash
# Update .env with new password
nano .env

# Update TradingView password at:
# www.tradingview.com → Account Settings → Security

# Restart scraper with new credentials
python tradingview_scraper.py
```

### Compromised Credentials

If credentials are exposed:

1. **Immediately change TradingView password**
   - Go to www.tradingview.com → Settings
   - Change password to strong, unique value
   - Sign out all sessions

2. **Update .env file**
   - Edit .env with new password
   - Delete old .env backup

3. **Review account activity**
   - Check TradingView for unauthorized trades
   - Monitor paper trading account for changes

4. **Notify support if needed**
   - Contact TradingView support if unauthorized access

---

## Final Checklist

Before running scripts in production:

- [ ] .env file created with credentials
- [ ] .env is in .gitignore
- [ ] Credentials load without errors
- [ ] Logs don't contain credentials
- [ ] .env is NOT committed to Git
- [ ] Password is strong (12+ chars, mixed case)
- [ ] Only TradingView paper trading enabled (no real money)

---

## Support

If credentials aren't loading:

```bash
# Check .env exists
ls -la .env
# Should show file with your credentials (will show with cat)

# Check environment variables
python -c "import os; print(os.getenv('TRADINGVIEW_EMAIL'))"
# Should print your email (or None if not loaded)

# Check python-dotenv is installed
pip install python-dotenv

# Reinstall all dependencies
pip install -r requirements.txt
```

---

**Your credentials are safe when using .env + environment variables.** ✅
