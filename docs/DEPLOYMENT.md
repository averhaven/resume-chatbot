# Deployment Guide: Cloud Run + Neon

Deploy the resume chatbot to Google Cloud Run (free tier) with Neon PostgreSQL (free tier).

> **Status**: Successfully deployed at https://resume-chatbot-vfczoegceq-ey.a.run.app

---

## Cost Protection Setup (Recommended First Step)

GCP does **not** automatically cap spending. Set up automatic shutdown to avoid unexpected bills.

### Create Budget with Pub/Sub Notification

```bash
export PROJECT_ID="your-project-id"
export BILLING_ACCOUNT_ID="your-billing-account-id"  # Find at: https://console.cloud.google.com/billing

# Enable required APIs
gcloud services enable cloudbilling.googleapis.com cloudfunctions.googleapis.com pubsub.googleapis.com --project=$PROJECT_ID

# Create Pub/Sub topic for budget alerts
gcloud pubsub topics create budget-alerts --project=$PROJECT_ID

# Create budget (€5 limit) with Pub/Sub notification
gcloud billing budgets create \
  --billing-account=$BILLING_ACCOUNT_ID \
  --display-name="Cost Cap €5" \
  --budget-amount=5EUR \
  --threshold-rule=percent=0.5,basis=current-spend \
  --threshold-rule=percent=0.9,basis=current-spend \
  --threshold-rule=percent=1.0,basis=current-spend \
  --notifications-rule-pubsub-topic=projects/$PROJECT_ID/topics/budget-alerts
```

### Deploy Auto-Shutdown Cloud Function

Create a Cloud Function that disables billing when budget is exceeded:

```bash
# Create function directory
mkdir -p /tmp/budget-function && cd /tmp/budget-function

# Create main.py
cat > main.py << 'PYEOF'
import base64
import json
import os
from googleapiclient import discovery

def stop_billing(data, context):
    pubsub_data = base64.b64decode(data['data']).decode('utf-8')
    pubsub_json = json.loads(pubsub_data)
    cost_amount = pubsub_json['costAmount']
    budget_amount = pubsub_json['budgetAmount']

    if cost_amount >= budget_amount:
        project_id = os.environ.get('GCP_PROJECT')
        billing = discovery.build('cloudbilling', 'v1', cache_discovery=False)

        # Disable billing
        billing.projects().updateBillingInfo(
            name=f'projects/{project_id}',
            body={'billingAccountName': ''}
        ).execute()

        print(f'Billing disabled for {project_id}. Cost: {cost_amount}, Budget: {budget_amount}')
    else:
        print(f'Under budget. Cost: {cost_amount}, Budget: {budget_amount}')
PYEOF

# Create requirements.txt
cat > requirements.txt << 'EOF'
google-api-python-client>=2.0.0
EOF

# Deploy the function
gcloud functions deploy stop-billing \
  --gen2 \
  --runtime=python312 \
  --region=europe-west3 \
  --source=. \
  --entry-point=stop_billing \
  --trigger-topic=budget-alerts \
  --set-env-vars=GCP_PROJECT=$PROJECT_ID \
  --project=$PROJECT_ID

# Grant billing admin permission to the function's service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/billing.projectManager"
```

### What Happens When Budget is Exceeded

1. GCP detects spending >= €5
2. Sends message to Pub/Sub topic
3. Cloud Function triggers and disables billing
4. **All GCP services stop** (Cloud Run, etc.)
5. You receive email notification

### Re-enable After Shutdown

```bash
# Re-link billing account to project
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT_ID
```

### Important Notes

- There's a **delay** (up to a few hours) between incurring costs and receiving alerts
- You might exceed €5 slightly before shutdown triggers
- Neon (external) will continue running - only GCP services stop
- Consider setting budget to €4 to account for delay

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERNET                                  │
└─────────────────────────────────────────────────────────────────┘
         │                                    │
         │ HTTPS (API requests)               │ PostgreSQL over TLS
         ▼                                    ▼
┌─────────────────────┐              ┌─────────────────────┐
│    Google Cloud     │              │       Neon          │
│     Cloud Run       │──────────────│    PostgreSQL       │
│                     │   Outbound   │                     │
│  - FastAPI app      │   connection │  - Serverless       │
│  - Scales 0-N       │   over TLS   │  - PgBouncer pooler │
└─────────────────────┘              └─────────────────────┘
```

| Component | Service | Free Tier |
|-----------|---------|-----------|
| Application | Google Cloud Run | 2M requests/mo |
| Database | Neon PostgreSQL | 0.5 GB storage, 100 CU-hours/mo |
| CI/CD | GitHub Actions | 2,000 mins/mo |

---

## Prerequisites

- Google Cloud account with billing enabled
- Neon account (free at https://neon.tech)
- GitHub repository with this codebase

---

## Step 1: Neon Database Setup

1. Go to https://console.neon.tech
2. Create a new project (free tier)
3. Copy the **pooled** connection string (with `-pooler` suffix):
   ```
   postgresql://user:password@ep-cool-name-123456-pooler.us-east-2.aws.neon.tech/dbname?sslmode=require
   ```
4. For SQLAlchemy, prefix with `+asyncpg`:
   ```
   postgresql+asyncpg://user:password@ep-cool-name-123456-pooler.us-east-2.aws.neon.tech/dbname?sslmode=require
   ```

---

## Step 2: GCP Project Setup

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="europe-west3"

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  --project=$PROJECT_ID

# Create Artifact Registry repository
gcloud artifacts repositories create cloud-run \
  --repository-format=docker \
  --location=$REGION \
  --project=$PROJECT_ID

# Create secrets
echo -n "postgresql+asyncpg://your-neon-connection-string" | \
  gcloud secrets create neon-database-url \
  --data-file=- \
  --project=$PROJECT_ID

echo -n "sk-or-your-openrouter-key" | \
  gcloud secrets create openrouter-api-key \
  --data-file=- \
  --project=$PROJECT_ID
```

---

## Step 3: Workload Identity Federation (for GitHub Actions)

This allows GitHub Actions to deploy without storing GCP credentials.

```bash
# Create a service account
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions" \
  --project=$PROJECT_ID

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:github-actions@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Create Workload Identity Pool
gcloud iam workload-identity-pools create "github" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --project=$PROJECT_ID

# Create Provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --project=$PROJECT_ID

# Allow GitHub repo to impersonate service account
# Replace GITHUB_ORG/REPO with your actual org/repo
gcloud iam service-accounts add-iam-policy-binding \
  github-actions@$PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')/locations/global/workloadIdentityPools/github/attribute.repository/GITHUB_ORG/REPO" \
  --project=$PROJECT_ID

# Get the WIF provider resource name (save this for GitHub secrets)
echo "WIF_PROVIDER: projects/$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')/locations/global/workloadIdentityPools/github/providers/github-provider"
echo "WIF_SERVICE_ACCOUNT: github-actions@$PROJECT_ID.iam.gserviceaccount.com"
```

---

## Step 4: GitHub Repository Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

| Secret Name | Value |
|-------------|-------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `WIF_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github-provider` |
| `WIF_SERVICE_ACCOUNT` | `github-actions@PROJECT_ID.iam.gserviceaccount.com` |

---

## Step 5: Deploy

### Automatic Deployment
Push to the `main` branch to trigger automatic deployment via GitHub Actions.

### Manual Deployment
```bash
cd backend

# Build and push image
gcloud builds submit \
  --tag $REGION-docker.pkg.dev/$PROJECT_ID/cloud-run/resume-chatbot \
  --project=$PROJECT_ID

# Deploy to Cloud Run
gcloud run deploy resume-chatbot \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run/resume-chatbot \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="LOG_LEVEL=INFO,RESUME_PATH=data/resume.json,LLM_MODEL=meta-llama/llama-3.2-3b-instruct:free,LLM_TIMEOUT=60.0" \
  --set-secrets="DATABASE_URL=neon-database-url:latest,OPENROUTER_API_KEY=openrouter-api-key:latest" \
  --project=$PROJECT_ID
```

---

## Step 6: Verify Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe resume-chatbot \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format='value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Test WebSocket (requires wscat: npm install -g wscat)
wscat -c "wss://${SERVICE_URL#https://}/ws"
```

---

## Deployment Flow

```
1. Push to main branch
         │
         ▼
2. GitHub Actions: Run tests (CI workflow)
         │
         ▼
3. GitHub Actions: Build Docker image
         │
         ▼
4. Push image to Artifact Registry
         │
         ▼
5. Deploy to Cloud Run
         │
         ▼
6. Cloud Run starts container:
   - Runs: alembic upgrade head (migrations)
   - Runs: uvicorn app.main:app
         │
         ▼
7. App connects to Neon PostgreSQL
```

---

## Running Migrations

Migrations run automatically on container startup. To run manually:

```bash
# From local machine (pointing to Neon)
cd backend
DATABASE_URL="postgresql+asyncpg://..." uv run alembic upgrade head

# Or via Cloud Run job (one-off)
gcloud run jobs execute migrate \
  --region=$REGION \
  --project=$PROJECT_ID
```

---

## Cost Estimate

| Service | Free Allowance | Expected Usage |
|---------|---------------|----------------|
| Cloud Run | 2M requests/mo | Low |
| Cloud Run | 360K GiB-sec/mo | Low |
| Neon | 100 CU-hours/mo | Low |
| Neon | 0.5 GB storage | Sufficient |
| Artifact Registry | 0.5 GB/mo | ~100MB |

**Expected monthly cost: $0** (within free tiers)

---

## WebSocket Considerations

Cloud Run has a **60-minute WebSocket timeout**. Implement client-side reconnection:

```javascript
let ws;
let reconnectAttempts = 0;

function connect(sessionId) {
  const url = sessionId
    ? `wss://your-service.run.app/ws?session_id=${sessionId}`
    : 'wss://your-service.run.app/ws';

  ws = new WebSocket(url);

  ws.onclose = () => {
    if (reconnectAttempts < 5) {
      setTimeout(() => {
        reconnectAttempts++;
        connect(sessionId); // Resume with same session
      }, 1000 * reconnectAttempts);
    }
  };

  ws.onopen = () => reconnectAttempts = 0;
}
```

The backend already supports session resumption via the `session_id` query parameter.

---

## Troubleshooting

### View Logs
```bash
gcloud run services logs read resume-chatbot \
  --region=$REGION \
  --project=$PROJECT_ID
```

### Check Service Status
```bash
gcloud run services describe resume-chatbot \
  --region=$REGION \
  --project=$PROJECT_ID
```

### Database Connection Issues
- Ensure you're using the **pooled** connection string (with `-pooler`)
- Verify `sslmode=require` is in the connection string
- Check Neon dashboard for connection logs

### Cold Start Issues
- First request after idle period may be slow (cold start)
- Cloud Run scales to zero when not in use
- Neon also scales to zero - first query wakes it up
