## Better Auth & Drizzle ORM Setup

### 1. Installation
We have installed the following packages:
```bash
# Core authentication and serverless PostgreSQL dependencies
pnpm add better-auth @better-auth/drizzle-adapter drizzle-orm@rc @neondatabase/serverless dotenv

# Development tools for migrations and typescript execution
pnpm add -D drizzle-kit@rc tsx
```

### 2. Environment Variables (.env)
Add the following to your `client/.env` file:
```env
BETTER_AUTH_SECRET=your_auth_secret
BETTER_AUTH_URL=http://localhost:3000

DATABASE_URL=postgresql://neondb_owner:[password]@ep-rapid-lake-atjv9dpn-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require

# Google OAuth Credentials (configured in Google Cloud Console)
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
```

### 3. File Layout
- **Database Client**: `client/src/db/index.ts`
- **Database Schema**: `client/src/db/schema.ts` (Tables: user, session, account, verification)
- **Database Relations**: `client/src/db/relations.ts` (Migrated to Drizzle ORM v1.0 Relational Queries v2 API)
- **Drizzle Kit Config**: `client/drizzle.config.ts`
- **Better Auth Backend Config**: `client/src/lib/auth.ts`
- **Better Auth Client Config**: `client/src/lib/auth-client.ts`
- **Better Auth Route Handler**: `client/src/app/api/auth/[...all]/route.ts`

### 4. Database Schema Migrations
To push changes to the database:
```bash
npx drizzle-kit push
```

### 5. Google OAuth Setup
1. Create a project in the **Google Cloud Console**.
2. Set up **OAuth Consent Screen** (External).
3. Create **OAuth Client ID** for Web Application:
   - **Authorized JavaScript Origin**: `http://localhost:3000`
   - **Authorized Redirect URI**: `http://localhost:3000/api/auth/callback/google`
4. Copy the Client ID and Client Secret into your `.env` file.