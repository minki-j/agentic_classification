# Authentication Setup Guide

This guide explains how to set up Google OAuth authentication for the Self-Evolving Taxonomy Agent.

## Prerequisites

1. A Google Cloud Project with OAuth 2.0 credentials
2. Backend server running on `http://localhost:8000`
3. Frontend running on `http://localhost:5173` (default Vite port)

## Backend Configuration

1. **Update your backend `.env` file** with your Google OAuth credentials:

```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5173/auth/callback
```

**Important**: The `GOOGLE_REDIRECT_URI` should point to your **frontend's** callback URL, not the backend's.

2. **Add CORS origins** in your backend `.env`:

```env
BACKEND_CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

## Frontend Configuration

1. **Copy the example environment file**:
```bash
cp .env.example .env
```

2. **Update the `.env` file** if your backend runs on a different port:
```env
VITE_API_URL=http://localhost:8000
```

## Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Enable Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Choose "Web application"
6. Add authorized redirect URIs:
   - `http://localhost:5173/auth/callback`
   - `http://localhost:3000/auth/callback` (if using different port)

## Authentication Flow

1. User clicks "Continue with Google" on the login page
2. Frontend requests OAuth URL from backend (`/api/v1/auth/google/login/redirect`)
3. Backend returns Google OAuth authorization URL
4. Frontend redirects user to Google
5. User authenticates with Google
6. Google redirects to frontend callback (`/auth/callback`)
7. Frontend sends auth code to backend (`/api/v1/auth/google/callback`)
8. Backend exchanges code for tokens and returns JWT tokens
9. Frontend stores tokens and fetches user data
10. User is redirected to the protected home page

## Security Notes

- JWT tokens are stored in localStorage
- Access tokens expire after 30 minutes
- Refresh tokens expire after 7 days
- The frontend automatically refreshes expired access tokens
- All API requests include the Authorization header with the JWT token

## Troubleshooting

### "Failed to authenticate with Google"
- Check that your Google OAuth credentials are correct
- Verify the redirect URI matches exactly in Google Console and backend config
- Ensure the backend server is running

### CORS errors
- Make sure your frontend URL is in the `BACKEND_CORS_ORIGINS` list
- Check that the backend is running on the expected port

### "User not found or inactive"
- This occurs when a user's refresh token is used but the user has been deleted
- User needs to log in again

## Development Tips

1. The authentication state is managed by `AuthContext`
2. Use the `useAuth` hook to access user data and auth functions
3. Wrap protected routes with the `ProtectedRoute` component
4. The `api` client in `lib/api.ts` automatically adds auth headers 