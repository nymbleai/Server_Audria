# Deployment Guide for Render (Option A: GCP Service Account)

This guide will help you deploy the Codraft Mini Backend to Render with your existing PostgreSQL database and Google Cloud Storage using a service account.

## Prerequisites

1. Render account ✅ (You have this)
2. Google Cloud Platform account with billing enabled
3. Existing PostgreSQL database on Render ✅ (You have this)

## Step 1: Setup Google Cloud Storage

### Create a Service Account
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **IAM & Admin** → **Service Accounts**
3. Click **Create Service Account**
4. Name: `codraft-storage-service`
5. Description: `Service account for Codraft file storage`
6. Click **Create and Continue**
7. Grant roles:
   - `Storage Admin` (for bucket management)
   - `Storage Object Admin` (for file operations)
8. Click **Continue** then **Done**
9. Click on the created service account
10. Go to **Keys** tab → **Add Key** → **Create New Key** → **JSON**
11. Download and save the JSON file securely

### Create a Storage Bucket
1. Go to **Cloud Storage** → **Buckets**
2. Click **Create Bucket**
3. Name: `codraft-production` (or your preferred name)
4. Location: Choose same region as your Render service for better performance
5. Storage class: **Standard**
6. Access control: **Uniform**
7. Click **Create**

### Set Bucket Permissions (Optional but Recommended)
1. Go to your bucket → **Permissions** tab
2. Click **Grant Access**
3. Add your service account email
4. Role: **Storage Object Admin**
5. Save

## Step 2: Deploy to Render

### Configure Environment Variables
In your Render web service settings, add/update these environment variables:

#### Required Variables
```bash
# Environment
ENVIRONMENT=production

# Database - IMPORTANT: Set this in Render environment variables, NOT in render.yaml
# NOTE: Must use postgresql+asyncpg:// (not postgresql://) for async support
DATABASE_URL=

# Google Cloud Storage - CRITICAL SETUP
GOOGLE_APPLICATION_CREDENTIALS=[Paste the entire JSON content from step 1]
GCS_BUCKET_NAME=codraft-production

# Other required variables
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
STRIPE_SECRET=your-stripe-secret-key
STRIPE_WEBHOOK_SECRET=your-webhook-secret
STRIPE_PRICE_FREE=your-free-price-id
STRIPE_PRICE_PREMIUM=your-premium-price-id
OPENAI_API_KEY=your-openai-api-key
FRONTEND_URL=https://your-frontend-domain.com
JWT_SECRET_KEY=your-secure-jwt-secret
```

#### 🚨 CRITICAL: Setting up GOOGLE_APPLICATION_CREDENTIALS

**Step-by-step:**
1. Open the JSON file you downloaded from Google Cloud
2. Copy the **entire JSON content** (it will look like this):
   ```json
   {
     "type": "service_account",
     "project_id": "your-project-id",
     "private_key_id": "key-id",
     "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
     "client_email": "codraft-storage-service@your-project.iam.gserviceaccount.com",
     "client_id": "...",
     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
     "token_uri": "https://oauth2.googleapis.com/token",
     ...
   }
   ```
3. In Render, paste this **entire JSON content** as the value for `GOOGLE_APPLICATION_CREDENTIALS`
4. Make sure it's all on one line with no extra spaces

**❌ DO NOT:**
- Paste a file path
- Upload the JSON file anywhere
- Modify the JSON content

**✅ DO:**
- Paste the complete JSON content as text
- Keep all quotes and formatting intact
- Ensure it starts with `{` and ends with `}`

## Step 3: Deploy Your Application

### Method 1: Using render.yaml (Recommended)
1. Your `render.yaml` is already configured
2. Push your changes to your repository
3. Render will automatically deploy

### Method 2: Manual Deploy
1. In Render dashboard, go to your web service
2. Click **Manual Deploy** → **Deploy latest commit**

## Step 4: Run Database Migrations

After your service is deployed:

1. In Render dashboard, go to your web service
2. Click **Shell** (or use the console)
3. Run: `alembic upgrade head`

Or create a one-time job:
1. Render Dashboard → **New** → **Job**
2. Command: `alembic upgrade head`
3. Run once

## Step 5: Verify Deployment

### Test Endpoints
- Health check: `https://your-service-name.onrender.com/health`
- API docs: `https://your-service-name.onrender.com/docs`

### Test File Storage
Check the logs to ensure GCS connection is successful. You should see:
```
✅ Google Cloud Storage client initialized successfully
```

## Troubleshooting

### Issue 1: "Failed to initialize Google Cloud Storage client"
**Cause**: Invalid JSON in `GOOGLE_APPLICATION_CREDENTIALS`
**Solution**: 
- Verify the JSON is complete and valid
- Check for extra spaces or line breaks
- Re-copy from the original downloaded file

### Issue 2: "Bucket does not exist"
**Cause**: Bucket name mismatch
**Solution**: 
- Verify `GCS_BUCKET_NAME` matches your actual bucket name
- Check bucket exists in Google Cloud Console

### Issue 3: "Permission denied"
**Cause**: Service account lacks permissions
**Solution**:
- Verify service account has `Storage Admin` role
- Check bucket permissions include your service account

### Issue 4: Database connection fails
**Cause**: Your database connection string has changed
**Solution**: 
- Get the latest connection string from Render PostgreSQL dashboard
- Update `DATABASE_URL` in environment variables

## Next Steps

1. **Test file upload/download** functionality
2. **Monitor logs** for any issues
3. **Set up monitoring** in Google Cloud Console
4. **Configure CORS** if needed for your frontend

## Security Notes

🚨 **CRITICAL SECURITY REMINDERS:**

- **Database credentials**: Set `DATABASE_URL` in Render's environment variables only - NEVER in render.yaml
- **GCP credentials**: Set `GOOGLE_APPLICATION_CREDENTIALS` in Render's environment variables only - NEVER commit JSON to git
- **render.yaml**: Uses `sync: false` for all secrets - this tells Render to read from environment variables
- **Never commit credentials** to your repository
- **Rotate credentials** periodically
- **Monitor GCP usage and billing**

### What goes in render.yaml vs Environment Variables:
- ✅ **render.yaml**: Non-sensitive config like `ENVIRONMENT=production` 
- ❌ **render.yaml**: Never put passwords, API keys, connection strings
- ✅ **Environment Variables**: All secrets (DATABASE_URL, API keys, credentials)

---

Your application should now be fully deployed with PostgreSQL and GCS! 🚀 