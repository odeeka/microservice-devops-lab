-- Initialize database schema
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2),
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_active ON items(is_active);
CREATE INDEX IF NOT EXISTS idx_items_created_at ON items(created_at);

-- Insert sample data
INSERT INTO items (name, description, price, category) VALUES
('Laptop', 'High-performance laptop', 999.99, 'Electronics'),
('Coffee Mug', 'Ceramic coffee mug', 12.99, 'Home & Kitchen'),
('Book', 'Programming guide', 39.99, 'Books'),
('Wireless Mouse', 'Ergonomic wireless mouse', 25.99, 'Electronics')
ON CONFLICT DO NOTHING;