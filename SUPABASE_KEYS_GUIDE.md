# Supabase API Keys Management Guide

This guide explains how to get, update, and switch between Supabase API keys.

## Understanding Supabase Keys

Supabase provides two types of API keys:

1. **Anon/Public Key** - Safe to use in client-side code (browser, mobile apps)
   - Has Row Level Security (RLS) policies enforced
   - Users can only access data they're allowed to see
   - Use this for frontend applications

2. **Service Role Key** - **SECRET** - Only for server-side use
   - Bypasses RLS policies
   - Full database access
   - **NEVER expose this in client-side code**
   - Use this for backend services (like your FastAPI server)

## Getting Your Supabase Keys

### Step 1: Access Supabase Dashboard

1. Go to [https://supabase.com](https://supabase.com)
2. Sign in to your account
3. Select your project (or create a new one)

### Step 2: Navigate to API Settings

1. In your project dashboard, click on **Settings** (gear icon in sidebar)
2. Click on **API** in the settings menu
3. You'll see two sections:
   - **Project API keys**
   - **Project URL**

### Step 3: Copy Your Keys

You'll see:
- **Project URL**: `https://xxxxx.supabase.co`
- **anon/public key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (starts with `eyJ`)
- **service_role key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (starts with `eyJ`)

⚠️ **Important**: The service_role key is hidden by default. Click "Reveal" to see it.

## Updating Keys in Your Project

### Option 1: Update .env File (Recommended)

1. Navigate to your project:
   ```bash
   cd Audria_server
   ```

2. Open or create `.env` file:
   ```bash
   # If file doesn't exist, copy from example
   cp env.example .env
   ```

3. Edit `.env` file and add your keys:
   ```env
   # Supabase Configuration
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Use service_role key for backend
   
   # Other settings
   FRONTEND_URL=http://localhost:8080
   JWT_SECRET_KEY=your-jwt-secret-key-change-this
   ENVIRONMENT=development
   ```

4. **Restart your server** for changes to take effect:
   ```bash
   # Stop the server (Ctrl+C) and restart
   poetry run uvicorn app.main:app --reload
   ```

### Option 2: Set Environment Variables Directly

```bash
export SUPABASE_URL="https://xxxxx.supabase.co"
export SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Which Key Should You Use?

### For Backend (FastAPI Server) - Use Service Role Key

Your backend needs the **service_role** key because:
- It needs to bypass RLS to manage user data
- It needs to perform admin operations
- It needs to access auth.users table

**In your `.env` file:**
```env
SUPABASE_KEY=eyJ...service_role_key_here
```

### For Frontend (React App) - Use Anon Key

Your frontend should use the **anon/public** key:
- It's safe to expose in client-side code
- RLS policies protect your data
- Users can only access their own data

**In your frontend `.env` file:**
```env
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...anon_key_here
```

## Rotating Keys (Creating New Keys)

If you need to rotate your keys for security:

### Step 1: Generate New Keys in Supabase

1. Go to **Settings** → **API**
2. Scroll down to **Project API keys**
3. Click **Reset** next to the key you want to rotate
4. Confirm the reset
5. **Copy the new key immediately** (you won't see it again)

### Step 2: Update All Places Using the Key

1. **Backend `.env` file**:
   ```env
   SUPABASE_KEY=new_service_role_key_here
   ```

2. **Frontend `.env` file** (if using anon key):
   ```env
   VITE_SUPABASE_ANON_KEY=new_anon_key_here
   ```

3. **Deployment environments** (Render, Vercel, etc.):
   - Update environment variables in your hosting platform

4. **Restart services**:
   - Restart your backend server
   - Rebuild/redeploy your frontend

## Switching Between Projects

If you want to switch to a different Supabase project:

1. **Get keys from new project** (follow steps above)
2. **Update `.env` file** with new URL and keys
3. **Update frontend** with new URL and anon key
4. **Restart services**

## Verifying Your Keys Work

### Test Backend Connection

```bash
cd Audria_server
poetry run python -c "
from app.services.supabase_service import supabase_service
print('✅ Supabase connected!' if supabase_service.supabase else '❌ Connection failed')
"
```

### Test Frontend Connection

In your browser console (on your frontend app):
```javascript
// Should print your Supabase client info
console.log(supabase);
```

## Security Best Practices

1. **Never commit `.env` files** to git
   - Already in `.gitignore` ✅

2. **Use different keys for different environments**:
   - Development: Use dev project keys
   - Production: Use production project keys

3. **Rotate keys regularly**:
   - Especially if a key is exposed
   - After team member leaves
   - Quarterly as a security practice

4. **Service Role Key = Admin Access**:
   - Treat it like a database password
   - Only use in server-side code
   - Never log it or expose it

5. **Use environment-specific configs**:
   ```env
   # .env.development
   SUPABASE_URL=https://dev-project.supabase.co
   SUPABASE_KEY=dev_service_role_key
   
   # .env.production
   SUPABASE_URL=https://prod-project.supabase.co
   SUPABASE_KEY=prod_service_role_key
   ```

## Troubleshooting

### "Supabase client not initialized"
- Check that `SUPABASE_URL` and `SUPABASE_KEY` are set in `.env`
- Verify the keys are correct (no extra spaces)
- Restart your server after updating `.env`

### "Invalid API key"
- Verify you copied the entire key (they're very long)
- Check for extra spaces or line breaks
- Make sure you're using the right key type (service_role for backend)

### "Permission denied" errors
- If using anon key on backend, switch to service_role key
- Check RLS policies are set up correctly
- Verify the key hasn't been rotated

## Quick Reference

```bash
# View current Supabase config (without exposing keys)
cd Audria_server
grep SUPABASE .env | sed 's/=.*/=***hidden***/'

# Test connection
poetry run python -c "from app.core.config import settings; print(f'URL: {settings.supabase_url[:30]}...')"
```

## Next Steps

1. ✅ Get your keys from Supabase dashboard
2. ✅ Update `.env` file with service_role key
3. ✅ Update frontend with anon key (if needed)
4. ✅ Restart your servers
5. ✅ Test the connection

Need help? Check the Supabase docs: https://supabase.com/docs/guides/api

