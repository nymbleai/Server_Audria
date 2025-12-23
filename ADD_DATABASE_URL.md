# How to Get DATABASE_URL from Supabase

The server needs `DATABASE_URL` to connect to Supabase's PostgreSQL database for SQLAlchemy operations.

## Quick Steps

1. **Go to Supabase Dashboard**
   - https://supabase.com/dashboard
   - Select your project: `wkkolmzefzjoabnzfuhy`

2. **Get Connection String**
   - Click **Settings** (⚙️) → **Database**
   - Scroll to **Connection string** section
   - Select **URI** tab
   - Copy the connection string

3. **Format it correctly**
   - It should look like: `postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-west-1.pooler.supabase.com:5432/postgres`
   - Replace `[YOUR-PASSWORD]` with your actual database password
   - For SQLAlchemy, use port **5432** (direct connection, not pooler port 6543)
   - Change `postgresql://` to `postgresql+asyncpg://` for async support

4. **Add to .env file**
   ```bash
   cd Audria_server
   ```
   
   Add this line to `.env`:
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:YOUR_PASSWORD@aws-0-us-west-1.pooler.supabase.com:5432/postgres
   ```

## Example

If your connection string is:
```
postgresql://postgres.wkkolmzefzjoabnzfuhy:your-password@aws-0-us-west-1.pooler.supabase.com:5432/postgres
```

Your `.env` should have:
```env
DATABASE_URL=postgresql+asyncpg://postgres.wkkolmzefzjoabnzfuhy:your-password@aws-0-us-west-1.pooler.supabase.com:5432/postgres
```

## Important Notes

- **Password**: You set this when creating the Supabase project. If you forgot it, you can reset it in Supabase Dashboard → Settings → Database → Database password
- **Port**: Use **5432** for direct connection (not 6543 which is the pooler)
- **Protocol**: Use `postgresql+asyncpg://` for async SQLAlchemy (not just `postgresql://`)

## After Adding DATABASE_URL

Restart your server:
```bash
cd Audria_server
poetry run uvicorn app.main:app --reload
```

The server should now start without errors!

