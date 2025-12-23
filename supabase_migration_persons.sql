-- Migration: Create persons and person_details tables
-- Description: Multi-user profile management system with RLS
-- Created: 2025-01-XX

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create persons table
CREATE TABLE IF NOT EXISTS persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    generation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create person_details table
CREATE TABLE IF NOT EXISTS person_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID NOT NULL UNIQUE REFERENCES persons(id) ON DELETE CASCADE,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_persons_user_id ON persons(user_id);
CREATE INDEX IF NOT EXISTS idx_persons_created_at ON persons(created_at);
CREATE INDEX IF NOT EXISTS idx_person_details_person_id ON person_details(person_id);
CREATE INDEX IF NOT EXISTS idx_person_details_data ON person_details USING GIN(data);

-- Enable Row Level Security (RLS)
ALTER TABLE persons ENABLE ROW LEVEL SECURITY;
ALTER TABLE person_details ENABLE ROW LEVEL SECURITY;

-- RLS Policies for persons table
-- Policy: Users can only SELECT their own persons
CREATE POLICY "Users can view their own persons"
    ON persons
    FOR SELECT
    USING (auth.uid() = user_id);

-- Policy: Users can INSERT their own persons
CREATE POLICY "Users can insert their own persons"
    ON persons
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Policy: Users can UPDATE their own persons
CREATE POLICY "Users can update their own persons"
    ON persons
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Policy: Users can DELETE their own persons
CREATE POLICY "Users can delete their own persons"
    ON persons
    FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for person_details table
-- Policy: Users can SELECT person_details for their own persons
CREATE POLICY "Users can view their own person details"
    ON person_details
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM persons
            WHERE persons.id = person_details.person_id
            AND persons.user_id = auth.uid()
        )
    );

-- Policy: Users can INSERT person_details for their own persons
CREATE POLICY "Users can insert their own person details"
    ON person_details
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM persons
            WHERE persons.id = person_details.person_id
            AND persons.user_id = auth.uid()
        )
    );

-- Policy: Users can UPDATE person_details for their own persons
CREATE POLICY "Users can update their own person details"
    ON person_details
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM persons
            WHERE persons.id = person_details.person_id
            AND persons.user_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM persons
            WHERE persons.id = person_details.person_id
            AND persons.user_id = auth.uid()
        )
    );

-- Policy: Users can DELETE person_details for their own persons
CREATE POLICY "Users can delete their own person details"
    ON person_details
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM persons
            WHERE persons.id = person_details.person_id
            AND persons.user_id = auth.uid()
        )
    );

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers to automatically update updated_at
CREATE TRIGGER update_persons_updated_at
    BEFORE UPDATE ON persons
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_person_details_updated_at
    BEFORE UPDATE ON person_details
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE persons IS 'Stores general information about persons associated with users';
COMMENT ON TABLE person_details IS 'Stores detailed information about persons in JSONB format';
COMMENT ON COLUMN persons.user_id IS 'References auth.users(id) - links person to Supabase user';
COMMENT ON COLUMN persons.generation IS 'Generation identifier (e.g., "Baby Boomer", "Gen X", "Millennial")';
COMMENT ON COLUMN person_details.data IS 'JSONB structure containing residences, workHistory, personalInfo, and dailyRoutine';

-- Example JSONB structure for person_details.data:
-- {
--   "residences": [
--     {
--       "id": "1",
--       "zipCode": "90210",
--       "city": "Beverly Hills",
--       "state": "CA",
--       "fromYear": "1980",
--       "toYear": "1995",
--       "notes": "Family home"
--     }
--   ],
--   "workHistory": [
--     {
--       "id": "1",
--       "job": "Software Engineer",
--       "fromYear": "1990",
--       "toYear": "2010",
--       "notes": "Worked at tech company"
--     }
--   ],
--   "personalInfo": {
--     "interests": "Reading, gardening, classical music",
--     "personalityTraits": "Kind, patient, detail-oriented",
--     "spiritualPractices": "Daily meditation",
--     "comfortItems": "Favorite blanket, family photos",
--     "preferredGreeting": "Good morning, how are you today?",
--     "favoriteSongs": "Moonlight Sonata, Clair de Lune",
--     "healthConditions": "Mild arthritis, requires medication at 8am",
--     "sensitivities": "Loud noises, bright lights",
--     "sensoryPreferences": "Soft lighting, quiet environment"
--   },
--   "dailyRoutine": {
--     "wakeTime": "07:00",
--     "napTime": "14:00",
--     "sleepTime": "22:00"
--   }
-- }

