# Database Setup Guide

## Prerequisites
- Supabase project created
- Access to Supabase SQL Editor

## Setup Steps

### 1. Run the SQL Schema

1. Go to your Supabase Dashboard
2. Navigate to **SQL Editor**
3. Create a new query
4. Copy and paste the contents of `database_schema.sql`
5. Click **Run** to execute the SQL

### 2. Verify Tables Created

After running the SQL, verify that the following tables were created:
- `chat_sessions`
- `messages`

You can check in the **Table Editor** section of Supabase.

### 3. Verify RLS Policies

Check that Row Level Security (RLS) is enabled and policies are created:
- Go to **Authentication** → **Policies**
- Verify policies exist for both tables

## Database Schema Overview

### `chat_sessions` Table
- `id` (UUID): Primary key
- `user_id` (UUID): Foreign key to auth.users
- `assistant_id` (TEXT): Type of assistant (typeX, references, etc.)
- `created_at` (TIMESTAMPTZ): Session creation timestamp
- `updated_at` (TIMESTAMPTZ): Last update timestamp
- `message_count` (INTEGER): Number of messages in session

### `messages` Table
- `id` (UUID): Primary key
- `chat_session_id` (UUID): Foreign key to chat_sessions
- `content` (TEXT): Message content
- `role` (TEXT): Message role (user, assistant, system)
- `timestamp` (TIMESTAMPTZ): Message timestamp
- `source` (TEXT): Message source (internal, web)

## Security

Row Level Security (RLS) is enabled to ensure:
- Users can only access their own chat sessions
- Users can only view/modify messages from their own sessions
- All operations are scoped to the authenticated user

## Notes

- The schema uses UUIDs for all IDs
- Timestamps are stored in UTC (TIMESTAMPTZ)
- Foreign keys have CASCADE delete (deleting a session deletes its messages)
- Indexes are created for optimal query performance

