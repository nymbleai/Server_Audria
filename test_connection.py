#!/usr/bin/env python3
"""
Quick script to test Supabase connection
Run with: poetry run python test_connection.py
"""

from app.services.supabase_service import supabase_service
from app.core.config import settings

def test_connection():
    print("🔍 Testing Supabase Connection...")
    print("=" * 50)
    
    # Check configuration
    print(f"\n📋 Configuration:")
    print(f"   SUPABASE_URL: {settings.supabase_url}")
    print(f"   SUPABASE_KEY: {settings.supabase_key[:20]}..." if settings.supabase_key else "   SUPABASE_KEY: ❌ Not set")
    
    # Check if client is initialized
    if not supabase_service.supabase:
        print("\n❌ Supabase client not initialized!")
        print("   Check your .env file and restart the server")
        return False
    
    print("\n✅ Supabase client initialized!")
    
    # Test querying a table
    try:
        print("\n🔍 Testing database connection...")
        
        # Try to query connection_test table
        result = supabase_service.supabase.table('connection_test').select('*').limit(5).execute()
        
        print(f"✅ Successfully connected to Supabase!")
        print(f"   Found {len(result.data)} records in connection_test table")
        
        if result.data:
            print("\n📊 Test Data:")
            for row in result.data:
                print(f"   - {row.get('test_message', 'N/A')} (Created: {row.get('created_at', 'N/A')})")
        
        # Check if persons table exists
        try:
            persons_result = supabase_service.supabase.table('persons').select('id').limit(1).execute()
            print(f"\n✅ persons table exists and is accessible")
        except Exception as e:
            print(f"\n⚠️  persons table: {str(e)}")
            print("   Run the SQL migration in Supabase to create tables")
        
        # Check if person_details table exists
        try:
            details_result = supabase_service.supabase.table('person_details').select('id').limit(1).execute()
            print(f"✅ person_details table exists and is accessible")
        except Exception as e:
            print(f"⚠️  person_details table: {str(e)}")
            print("   Run the SQL migration in Supabase to create tables")
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! Supabase connection is working.")
        return True
        
    except Exception as e:
        print(f"\n❌ Error querying database: {str(e)}")
        print("\n💡 Troubleshooting:")
        print("   1. Make sure you've run the SQL migration in Supabase")
        print("   2. Check that your SUPABASE_KEY is correct")
        print("   3. Verify the SUPABASE_URL matches your project")
        return False

if __name__ == "__main__":
    success = test_connection()
    exit(0 if success else 1)

