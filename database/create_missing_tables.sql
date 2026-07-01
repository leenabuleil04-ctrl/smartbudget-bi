-- Create categories table
CREATE TABLE IF NOT EXISTS categories (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  icon TEXT,
  color TEXT
);

-- Insert default spending categories
INSERT INTO categories (name, icon, color) VALUES
('Food', '🍔', '#10B981'),
('Rent', '🏠', '#3B82F6'),
('Transport', '🚌', '#F59E0B'),
('Entertainment', '🎬', '#8B5CF6'),
('Education', '📚', '#06B6D4'),
('Health', '💊', '#EF4444'),
('Shopping', '🛍️', '#EC4899'),
('Other', '📦', '#94A3B8')
ON CONFLICT (name) DO NOTHING;

-- Create monthly summary table
CREATE TABLE IF NOT EXISTS monthly_summary (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID REFERENCES students(id) ON DELETE CASCADE,
  month TEXT NOT NULL,
  total_income NUMERIC(10,2) DEFAULT 0,
  total_expenses NUMERIC(10,2) DEFAULT 0,
  balance NUMERIC(10,2) DEFAULT 0,
  status TEXT DEFAULT 'on_track',
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(student_id, month)
);
