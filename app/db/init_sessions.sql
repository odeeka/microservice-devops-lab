-- Session Management Schema
-- Tracks all active user sessions for JWT tokens

-- Create user_sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(64) NOT NULL UNIQUE,  -- SHA256 hash of JWT token
    device_info VARCHAR(255),                    -- Device name/type
    ip_address INET,                             -- User's IP address
    user_agent TEXT,                             -- Browser/client user agent
    fingerprint_data JSONB,                      -- Device fingerprint and metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP,
    revoke_reason VARCHAR(100)                   -- 'logout', 'admin', 'expired', 'security'
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(user_id, is_revoked, expires_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions_fingerprint ON user_sessions USING GIN (fingerprint_data);

-- Add comment for documentation
COMMENT ON TABLE user_sessions IS 'Tracks all active JWT token sessions for users';
COMMENT ON COLUMN user_sessions.session_token IS 'SHA256 hash of the JWT access token';
COMMENT ON COLUMN user_sessions.is_revoked IS 'True if session was manually revoked (logout, admin action, etc)';
COMMENT ON COLUMN user_sessions.last_active IS 'Updated on each authenticated request';
COMMENT ON COLUMN user_sessions.fingerprint_data IS 'Device fingerprint: browser, OS, IP, risk analysis';
