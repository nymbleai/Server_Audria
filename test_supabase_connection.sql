-- Quick test to verify Supabase connection
-- This creates a simple test table that you can see in your Supabase dashboard

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create a simple test table to verify connection
CREATE TABLE IF NOT EXISTS connection_test (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    test_message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    server_name TEXT DEFAULT 'Audria Backend'
);

-- Insert a test record
INSERT INTO connection_test (test_message, server_name)
VALUES ('✅ Supabase connection successful!', 'Audria Backend')
ON CONFLICT DO NOTHING;

-- Create persons table (from main migration)
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

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_persons_user_id ON persons(user_id);
CREATE INDEX IF NOT EXISTS idx_persons_created_at ON persons(created_at);
CREATE INDEX IF NOT EXISTS idx_person_details_person_id ON person_details(person_id);
CREATE INDEX IF NOT EXISTS idx_person_details_data ON person_details USING GIN(data);

-- Enable Row Level Security (RLS)
ALTER TABLE persons ENABLE ROW LEVEL SECURITY;
ALTER TABLE person_details ENABLE ROW LEVEL SECURITY;

-- RLS Policies for persons table
DROP POLICY IF EXISTS "Users can view their own persons" ON persons;
CREATE POLICY "Users can view their own persons"
    ON persons FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own persons" ON persons;
CREATE POLICY "Users can insert their own persons"
    ON persons FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own persons" ON persons;
CREATE POLICY "Users can update their own persons"
    ON persons FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own persons" ON persons;
CREATE POLICY "Users can delete their own persons"
    ON persons FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for person_details table
DROP POLICY IF EXISTS "Users can view their own person details" ON person_details;
CREATE POLICY "Users can view their own person details"
    ON person_details FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM persons
            WHERE persons.id = person_details.person_id
            AND persons.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can insert their own person details" ON person_details;
CREATE POLICY "Users can insert their own person details"
    ON person_details FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM persons
            WHERE persons.id = person_details.person_id
            AND persons.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Users can update their own person details" ON person_details;
CREATE POLICY "Users can update their own person details"
    ON person_details FOR UPDATE
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

DROP POLICY IF EXISTS "Users can delete their own person details" ON person_details;
CREATE POLICY "Users can delete their own person details"
    ON person_details FOR DELETE
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

-- Create triggers
DROP TRIGGER IF EXISTS update_persons_updated_at ON persons;
CREATE TRIGGER update_persons_updated_at
    BEFORE UPDATE ON persons
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_person_details_updated_at ON person_details;
CREATE TRIGGER update_person_details_updated_at
    BEFORE UPDATE ON person_details
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Verify tables were created
SELECT 
    table_name,
    '✅ Created' as status
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('connection_test', 'persons', 'person_details')
ORDER BY table_name;

