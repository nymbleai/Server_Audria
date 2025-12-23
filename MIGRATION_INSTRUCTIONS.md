# Migration Instructions for Persons Tables

## Option 1: Supabase SQL Editor (Recommended - Easiest)

Since you're using Supabase, the easiest way is to run the SQL migration directly:

1. Open your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Copy the entire contents of `supabase_migration_persons.sql`
4. Paste and run it in the SQL Editor

This will create:
- ✅ Both tables (`persons` and `person_details`)
- ✅ All indexes
- ✅ Row Level Security (RLS) policies
- ✅ Triggers for automatic timestamp updates

**This is the recommended approach for Supabase projects.**

## Option 2: Alembic Migration (If you have DATABASE_URL set)

If you prefer to use Alembic migrations, you need to:

1. **Set the DATABASE_URL environment variable:**
   ```bash
   export DATABASE_URL="postgresql://postgres:[YOUR-PASSWORD]@[YOUR-PROJECT-REF].supabase.co:5432/postgres"
   ```
   
   Or add it to your `.env` file:
   ```
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@[YOUR-PROJECT-REF].supabase.co:5432/postgres
   ```

2. **Run the Alembic migration:**
   ```bash
   cd Audria_server
   poetry run alembic upgrade head
   ```

3. **Then run the SQL migration for RLS policies:**
   - The Alembic migration creates the table structure
   - You still need to run the SQL migration in Supabase SQL Editor to add RLS policies and triggers

## Getting Your Supabase Database URL

1. Go to your Supabase project dashboard
2. Navigate to **Settings** → **Database**
3. Find the **Connection string** section
4. Copy the **URI** connection string
5. Replace `[YOUR-PASSWORD]` with your actual database password

The format should be:
```
postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

For Alembic, use the direct connection (port 5432) instead of the pooler (port 6543):
```
postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-west-1.pooler.supabase.com:5432/postgres
```

## What Gets Created

### Tables
- `persons` - General person information (name, generation)
- `person_details` - Detailed information in JSONB format

### Security
- Row Level Security (RLS) enabled on both tables
- Policies ensure users can only access their own data

### Features
- Automatic timestamp updates via triggers
- Indexes for optimal query performance
- GIN index on JSONB data for efficient JSON queries

## Verification

After running the migration, verify it worked:

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('persons', 'person_details');

-- Check RLS is enabled
SELECT tablename, rowsecurity FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('persons', 'person_details');
```

Both should show `rowsecurity = true`.

