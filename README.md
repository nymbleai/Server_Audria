# Audria Backend API

FastAPI backend service for Audria with Supabase authentication.

## Features

- ✅ **Supabase Authentication** - Complete auth system (signup, signin, password reset)
- ✅ **JWT Token Management** - Automatic token refresh and validation
- ✅ **FastAPI** - Modern, fast (high-performance) web framework
- ✅ **Type Safety** - Full type hints with Pydantic models
- ✅ **CORS Support** - Configured for frontend integration
- ✅ **Health Checks** - Built-in health monitoring endpoints

## Tech Stack

- **Python 3.9+**
- **FastAPI** - Web framework
- **Supabase** - Authentication and database
- **Pydantic** - Data validation
- **Python-JOSE** - JWT token handling
- **Uvicorn** - ASGI server

## Prerequisites

- Python 3.9 or higher
- Poetry (recommended) or pip
- Supabase account and project

## Quick Start

### 1. Install Dependencies

**Using Poetry (recommended):**
```bash
cd server
poetry install
```

**Using pip:**
```bash
cd server
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the `server` directory:

```env
# Environment
ENVIRONMENT=development

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_role_key

# Frontend URL
FRONTEND_URL=http://localhost:5173

# JWT Configuration (optional)
JWT_SECRET_KEY=your-secret-key-change-this
```

### 3. Run the Server

**Using Poetry:**
```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Using Python:**
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup` | Register new user |
| POST | `/api/auth/signin` | Login user |
| POST | `/api/auth/signout` | Logout user |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/forgot-password` | Request password reset |
| POST | `/api/auth/reset-password` | Reset password |
| GET | `/api/auth/me` | Get current user info |
| GET | `/api/auth/status` | Check auth service status |

### Health Check

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check |

## Project Structure

```
server/
├── app/
│   ├── core/
│   │   ├── auth.py           # JWT authentication logic
│   │   └── config.py         # App configuration
│   ├── routers/
│   │   └── auth.py           # Authentication endpoints
│   ├── schemas/
│   │   └── auth.py           # Pydantic models
│   ├── services/
│   │   └── supabase_service.py  # Supabase client wrapper
│   └── main.py               # FastAPI app entry point
├── pyproject.toml            # Poetry dependencies
├── requirements.txt          # Pip dependencies
├── .env                      # Environment variables (create this)
└── README.md                 # This file
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | Application environment | `development`, `production` |
| `SUPABASE_URL` | Your Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_KEY` | Supabase service role key | `eyJhbGc...` |
| `FRONTEND_URL` | Frontend application URL | `http://localhost:5173` |
| `JWT_SECRET_KEY` | Secret key for JWT (optional) | Any secure random string |

## Authentication Flow

### 1. Sign Up
```bash
POST /api/auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "John Doe"
}
```

### 2. Sign In
```bash
POST /api/auth/signin
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}
```

### 3. Use Access Token
```bash
GET /api/auth/me
Authorization: Bearer <access_token>
```

### 4. Refresh Token
```bash
POST /api/auth/refresh
Authorization: Bearer <refresh_token>
```

## Development

### Running in Development Mode

```bash
# With auto-reload
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using the Poetry script
poetry run dev
```

### Code Formatting

```bash
# Format with black
poetry run black app/

# Sort imports
poetry run isort app/
```

### Testing

```bash
poetry run pytest
```

## Production Deployment

### Using Docker

A `Dockerfile` is included for containerized deployment:

```bash
# Build image
docker build -t audria-backend .

# Run container
docker run -p 8000:8000 --env-file .env audria-backend
```

### Environment Variables for Production

```env
ENVIRONMENT=production
SUPABASE_URL=https://your-production-project.supabase.co
SUPABASE_KEY=your_production_service_key
FRONTEND_URL=https://your-frontend-domain.com
JWT_SECRET_KEY=use-a-strong-random-key-here
```

### Production Server

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or use a process manager like PM2 or systemd.

## CORS Configuration

CORS is configured based on the environment:

- **Development**: Allows all origins (`*`)
- **Production**: Only allows `FRONTEND_URL`

Modify `app/main.py` if you need custom CORS settings.

## Supabase Integration

### Required Supabase Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Enable Email authentication in Authentication → Providers
3. Configure email templates (optional)
4. Get your project URL and service role key from Settings → API
5. Run the database migration from `supabase_migration.sql`

### Database Tables

The `profiles` table is automatically created via the migration script:

```sql
-- See supabase_migration.sql for complete schema
profiles (
  id UUID PRIMARY KEY,
  email VARCHAR,
  first_name VARCHAR,
  last_name VARCHAR,
  full_name VARCHAR,
  avatar_url TEXT,
  role user_role DEFAULT 'patient',
  ...
)
```

## Troubleshooting

### Common Issues

**1. Supabase client not initialized**
- Verify `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
- Check that you're using the **service role key**, not the anon key

**2. CORS errors**
- Update `FRONTEND_URL` in `.env`
- Check CORS middleware configuration in `main.py`

**3. JWT token errors**
- Ensure tokens are passed in `Authorization: Bearer <token>` header
- Check token expiration (refresh if needed)

**4. Password reset email not sending**
- Verify Supabase email settings
- Check Supabase email rate limits (free tier)
- Configure custom SMTP in Supabase (optional)

### Logs

The server logs to stdout. Check logs for detailed error messages:

```bash
# View logs in development
poetry run uvicorn app.main:app --reload --log-level debug
```

## Security Best Practices

1. **Never commit `.env` file** - It's in `.gitignore`
2. **Use strong JWT secret** - Generate a secure random key
3. **Rotate keys regularly** - Update Supabase keys periodically
4. **Use HTTPS in production** - Always use TLS/SSL
5. **Limit CORS origins** - Only allow your frontend domain
6. **Service role key protection** - Never expose in client code

## API Response Format

### Success Response
```json
{
  "success": true,
  "message": "Operation successful",
  "session": {
    "access_token": "...",
    "refresh_token": "...",
    "expires_in": 3600,
    "token_type": "bearer",
    "user": {
      "id": "...",
      "email": "...",
      ...
    }
  }
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

## Dependencies

### Production Dependencies
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `supabase` - Supabase client
- `python-jose` - JWT handling
- `pydantic` - Data validation
- `python-dotenv` - Environment management

### Development Dependencies
- `pytest` - Testing framework
- `black` - Code formatter
- `isort` - Import sorter

## Contributing

1. Follow the existing code style
2. Use type hints for all functions
3. Add docstrings to public methods
4. Format code with `black` and `isort`
5. Test your changes

## License

MIT License - feel free to use this project for your own purposes.

## Support

For issues or questions:
1. Check the API documentation at `/docs`
2. Review the Supabase documentation
3. Check server logs for error messages

## Changelog

### Version 1.0.0 (Current)
- Initial release
- Supabase authentication integration
- User signup/signin
- Password reset functionality
- Token refresh
- Health check endpoints

---

**Built with ❤️ for Audria**
