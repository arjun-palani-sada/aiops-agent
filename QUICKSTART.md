# ⚡ AIOps Agent - 15-Minute Quick Start

Get up and running with the AIOps Agent in 15 minutes!

---

## 🎯 Prerequisites Check (2 minutes)

```bash
# Check Python version (need 3.9+)
python3 --version

# Check gcloud CLI
gcloud --version

# Check if logged in
gcloud auth list

# If not logged in:
gcloud auth login
gcloud auth application-default login
```

---

## 📦 Part 1: Deploy Demo Service (5 minutes)

```bash
# 1. Clone demo service
git clone <demo-service-repo-url>
cd demo-service

# 2. Set your project
gcloud config set project YOUR_PROJECT_ID

# 3. Deploy
chmod +x deploy.sh
./deploy.sh

# 4. Save the service URL shown at the end
export SERVICE_URL=https://aiops-demo-service-xxx.us-central1.run.app
```

---

## 🤖 Part 2: Setup AIOps Agent (5 minutes)

```bash
# 1. Clone AIOps agent (in a separate directory)
cd ..
git clone <aiops-agent-repo-url>
cd aiops-agent-final

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -e .

# 4. Configure environment
cp .env.example .env

# 5. Edit .env (add your GCP project)
nano .env
# Set: GCP_PROJECT_ID=YOUR_PROJECT_ID
# Optional: GOOGLE_API_KEY=your-key (for AI features)
```

---

## 🧪 Part 3: Test End-to-End (5 minutes)

```bash
# 1. Generate traffic (creates errors)
cd ../demo-service
python3 generate_traffic_auth.py $SERVICE_URL 3

# 2. Wait for logs to propagate
echo "Waiting 2 minutes for logs..."
sleep 120

# 3. Run the AIOps Agent
cd ../aiops-agent-final
python3 test_aiops_agent.py aiops-demo-service

# 4. View results
# You should see:
# ✅ Root Cause: Permission errors detected
# ✅ Confidence: 85-95%
# ✅ Duration: 6-8 seconds
```

---

## 🎉 Success Criteria

You should see output like this:

```
======================================================================
🔍 General Health Check
======================================================================

✅ Investigation Successful

📊 Results:
   Service: aiops-demo-service
   Root Cause: Permission or authorization errors detected in 45/50 logs
   Confidence: 90%
   Duration: 6.50s
   Logs Analyzed: 50

💡 Recommended Actions:
   1. Verify IAM permissions
   2. Check service account configuration
   3. Review audit logs
```

---

## 🎯 Quick Commands Reference

### Demo Service

```bash
# Deploy
cd demo-service && ./deploy.sh

# Generate traffic
python3 generate_traffic_auth.py $SERVICE_URL 5

# Check logs
gcloud logging read "resource.labels.service_name=aiops-demo-service" --limit=10

# Delete service
gcloud run services delete aiops-demo-service --region=us-central1 --quiet
```

### AIOps Agent

```bash
# Test investigation
python3 test_aiops_agent.py aiops-demo-service

# Compare modes (rule-based vs AI)
python3 test_both_modes.py aiops-demo-service

# Test with custom service
python3 test_aiops_agent.py your-service-name
```

---

## 🐛 Common Issues

### "No logs found"
```bash
# Wait longer (logs take 2-3 minutes)
sleep 120

# Or generate more traffic
python3 generate_traffic_auth.py $SERVICE_URL 2
```

### "Permission denied"
```bash
# Re-authenticate
gcloud auth application-default login
```

### "Service not found"
```bash
# Check service name
gcloud run services list

# Verify it's deployed
gcloud run services describe aiops-demo-service --region=us-central1
```

---

## 🚀 What's Next?

### Test Different Error Types

```bash
# Permission errors
for i in {1..30}; do
  python3 -c "
import requests, subprocess
token = subprocess.check_output(['gcloud', 'auth', 'print-identity-token'], text=True).strip()
requests.get('$SERVICE_URL/api/permission', headers={'Authorization': f'Bearer {token}'})
"
done

# Wait and test
sleep 120
cd ../aiops-agent-final
python3 test_aiops_agent.py aiops-demo-service
```

### Enable AI Mode

```bash
# 1. Get API key from: https://makersuite.google.com/app/apikey

# 2. Add to .env
echo "GOOGLE_API_KEY=your-key" >> .env
echo "MODEL_NAME=gemini-2.0-flash" >> .env
echo "USE_LLM=true" >> .env

# 3. Test with AI
python3 test_both_modes.py aiops-demo-service
```

### Test Your Own Services

```bash
# Replace with your Cloud Run service name
python3 test_aiops_agent.py your-production-service
```

---

## 📚 Full Documentation

- [AIOps Agent README](README.md) - Complete documentation
- [Demo Service README](../demo-service/README.md) - Service details


---

## ⏱️ Time Breakdown

- ✅ Prerequisites: 2 min
- ✅ Deploy Demo Service: 5 min
- ✅ Setup AIOps Agent: 5 min
- ✅ Test End-to-End: 5 min
- **Total: ~15 minutes**

---

