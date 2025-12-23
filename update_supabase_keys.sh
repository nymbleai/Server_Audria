#!/bin/bash

# Script to help update Supabase keys
# Usage: ./update_supabase_keys.sh

echo "🔑 Supabase Keys Update Helper"
echo "================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from env.example..."
    cp env.example .env
    echo "✅ Created .env file"
    echo ""
fi

echo "Current Supabase configuration:"
echo "-------------------------------"
if grep -q "SUPABASE_URL" .env; then
    SUPABASE_URL=$(grep "SUPABASE_URL" .env | cut -d '=' -f2)
    if [ -z "$SUPABASE_URL" ]; then
        echo "❌ SUPABASE_URL is empty"
    else
        echo "✅ SUPABASE_URL: $SUPABASE_URL"
    fi
else
    echo "❌ SUPABASE_URL not found in .env"
fi

if grep -q "SUPABASE_KEY" .env; then
    SUPABASE_KEY=$(grep "SUPABASE_KEY" .env | cut -d '=' -f2)
    if [ -z "$SUPABASE_KEY" ]; then
        echo "❌ SUPABASE_KEY is empty"
    else
        KEY_PREVIEW="${SUPABASE_KEY:0:20}..."
        echo "✅ SUPABASE_KEY: $KEY_PREVIEW (hidden)"
    fi
else
    echo "❌ SUPABASE_KEY not found in .env"
fi

echo ""
echo "📋 To update your keys:"
echo "1. Go to https://supabase.com/dashboard"
echo "2. Select your project"
echo "3. Go to Settings → API"
echo "4. Copy your Project URL and Service Role Key"
echo ""
echo "5. Edit .env file and update:"
echo "   SUPABASE_URL=https://xxxxx.supabase.co"
echo "   SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
echo ""
echo "6. Restart your server:"
echo "   poetry run uvicorn app.main:app --reload"
echo ""

# Interactive mode
read -p "Do you want to update keys now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    read -p "Enter Supabase URL: " new_url
    read -p "Enter Supabase Service Role Key: " new_key
    
    # Update .env file
    if grep -q "SUPABASE_URL" .env; then
        sed -i.bak "s|SUPABASE_URL=.*|SUPABASE_URL=$new_url|" .env
    else
        echo "SUPABASE_URL=$new_url" >> .env
    fi
    
    if grep -q "SUPABASE_KEY" .env; then
        sed -i.bak "s|SUPABASE_KEY=.*|SUPABASE_KEY=$new_key|" .env
    else
        echo "SUPABASE_KEY=$new_key" >> .env
    fi
    
    # Clean up backup file
    rm -f .env.bak
    
    echo ""
    echo "✅ Keys updated in .env file"
    echo "⚠️  Don't forget to restart your server!"
fi

