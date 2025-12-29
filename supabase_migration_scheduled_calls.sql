-- Migration: Create scheduled_calls table
-- Description: Table for storing scheduled calls (single, recurring, or immediate)
-- Created: 2025-01-XX

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create scheduled_calls table
CREATE TABLE IF NOT EXISTS scheduled_calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    person_id UUID REFERENCES persons(id) ON DELETE SET NULL,
    agent_name VARCHAR(100) NOT NULL,
    call_type VARCHAR(20) NOT NULL,  -- 'single', 'recurring', 'immediate'
    scheduled_datetime TIMESTAMPTZ,  -- For single calls
    scheduled_time TIME,  -- For recurring calls (e.g., '09:00')
    recurrence_pattern JSONB,  -- For recurring calls: {"days_of_week": [...], "start_date": "...", "end_date": "..."}
    leading_reminders TEXT,
    leading_topics TEXT,
    memories JSONB,  -- Array of memory names: ["memory1", "memory2"]
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',  -- 'scheduled', 'completed', 'cancelled', 'missed', 'immediate'
    is_active BOOLEAN NOT NULL DEFAULT true,
    initiated_at TIMESTAMPTZ,  -- For immediate calls
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT false
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_scheduled_calls_id ON scheduled_calls(id);
CREATE INDEX IF NOT EXISTS idx_scheduled_calls_user_id ON scheduled_calls(user_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_calls_person_id ON scheduled_calls(person_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_calls_scheduled_datetime ON scheduled_calls(scheduled_datetime);
CREATE INDEX IF NOT EXISTS idx_scheduled_calls_is_active ON scheduled_calls(is_active);
CREATE INDEX IF NOT EXISTS idx_scheduled_calls_is_deleted ON scheduled_calls(is_deleted);

-- GIN indexes for JSONB columns (for efficient JSON queries)
CREATE INDEX IF NOT EXISTS idx_scheduled_calls_recurrence_pattern ON scheduled_calls USING GIN(recurrence_pattern);
CREATE INDEX IF NOT EXISTS idx_scheduled_calls_memories ON scheduled_calls USING GIN(memories);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS ix_scheduled_calls_user_active ON scheduled_calls(user_id, is_active, is_deleted);
CREATE INDEX IF NOT EXISTS ix_scheduled_calls_user_datetime ON scheduled_calls(user_id, scheduled_datetime);

-- Enable Row Level Security (RLS)
ALTER TABLE scheduled_calls ENABLE ROW LEVEL SECURITY;

-- RLS Policies for scheduled_calls table
-- Policy: Users can only SELECT their own scheduled calls
CREATE POLICY "Users can view their own scheduled calls"
    ON scheduled_calls
    FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Users can INSERT their own scheduled calls
CREATE POLICY "Users can insert their own scheduled calls"
    ON scheduled_calls
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Policy: Users can UPDATE their own scheduled calls
CREATE POLICY "Users can update their own scheduled calls"
    ON scheduled_calls
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Policy: Users can DELETE their own scheduled calls
CREATE POLICY "Users can delete their own scheduled calls"
    ON scheduled_calls
    FOR DELETE
    USING (auth.uid() = user_id);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_scheduled_calls_updated_at
    BEFORE UPDATE ON scheduled_calls
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE scheduled_calls IS 'Stores scheduled calls (single, recurring, or immediate) for users';
COMMENT ON COLUMN scheduled_calls.user_id IS 'References auth.users(id) - links scheduled call to Supabase user';
COMMENT ON COLUMN scheduled_calls.person_id IS 'References persons(id) - links scheduled call to a person (e.g., Bianca)';
COMMENT ON COLUMN scheduled_calls.call_type IS 'Type of call: single (one-time), recurring (repeating), or immediate (instant)';
COMMENT ON COLUMN scheduled_calls.scheduled_datetime IS 'Date and time for single calls';
COMMENT ON COLUMN scheduled_calls.scheduled_time IS 'Time of day for recurring calls (e.g., 09:00)';
COMMENT ON COLUMN scheduled_calls.recurrence_pattern IS 'JSONB structure for recurring calls: {"days_of_week": ["Monday", "Wednesday"], "start_date": "...", "end_date": "..."}';
COMMENT ON COLUMN scheduled_calls.memories IS 'JSONB array of memory names associated with the call';

