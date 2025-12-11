-- Add role column to users table for role-based access control
-- This migration adds ENUM column for 'user' or 'admin' roles

ALTER TABLE users 
ADD COLUMN role ENUM('user', 'admin') DEFAULT 'user' NOT NULL 
AFTER is_active;

-- Set initial admin users
UPDATE users 
SET role = 'admin' 
WHERE username IN ('fairflow', 'matthew', 'admin');
