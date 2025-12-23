#!/usr/bin/env python3
"""
Script to create test data that will be visible in Supabase dashboard
Run with: poetry run python create_test_data.py
"""

import asyncio
from app.services.supabase_service import supabase_service
from app.core.config import settings
import uuid

async def create_test_data():
    print("🧪 Creating Test Data for Supabase Dashboard...")
    print("=" * 60)
    
    if not supabase_service.supabase:
        print("❌ Supabase client not initialized!")
        print("   Make sure your .env file has SUPABASE_URL and SUPABASE_KEY")
        return
    
    print("\n✅ Supabase client connected!")
    
    # First, let's check if we have any users
    # For testing, we'll need a user_id
    # In a real scenario, this would come from authentication
    
    print("\n📝 Creating test data...")
    
    try:
        # Create a test person (you'll need to replace this with actual user_id from auth)
        # For now, we'll create data that can be seen in dashboard
        
        # Note: In production, user_id comes from authenticated user
        # For testing, you can get a user_id from Supabase Auth dashboard
        
        print("\n💡 To create test data:")
        print("   1. Go to Supabase Dashboard → Authentication → Users")
        print("   2. Copy a user ID (or create a test user)")
        print("   3. Update this script with that user_id")
        print("   4. Or use the Supabase dashboard to insert data directly")
        
        # Example: Create data directly in Supabase (bypasses RLS with service role)
        print("\n🔍 Checking existing tables...")
        
        # Check connection_test table
        try:
            test_result = supabase_service.supabase.table('connection_test').select('*').execute()
            print(f"✅ connection_test table: {len(test_result.data)} rows")
        except Exception as e:
            print(f"⚠️  connection_test: {str(e)}")
        
        # Check persons table
        try:
            persons_result = supabase_service.supabase.table('persons').select('*').limit(10).execute()
            print(f"✅ persons table: {len(persons_result.data)} rows")
            if persons_result.data:
                print("\n📊 Current persons:")
                for person in persons_result.data:
                    print(f"   - {person.get('name', 'N/A')} (ID: {person.get('id', 'N/A')[:8]}...)")
        except Exception as e:
            print(f"⚠️  persons table: {str(e)}")
            print("   Run the SQL migration first!")
        
        # Check person_details table
        try:
            details_result = supabase_service.supabase.table('person_details').select('*').limit(10).execute()
            print(f"✅ person_details table: {len(details_result.data)} rows")
        except Exception as e:
            print(f"⚠️  person_details: {str(e)}")
        
        print("\n" + "=" * 60)
        print("✅ Data check complete!")
        print("\n💡 To create new data:")
        print("   1. Use your app's API endpoints")
        print("   2. Or insert directly in Supabase Table Editor")
        print("   3. Data will appear in dashboard immediately!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\n💡 Make sure:")
        print("   1. SQL migration has been run in Supabase")
        print("   2. Tables exist (persons, person_details)")
        print("   3. Your SUPABASE_KEY has proper permissions")

if __name__ == "__main__":
    asyncio.run(create_test_data())

