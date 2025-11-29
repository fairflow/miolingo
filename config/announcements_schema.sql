-- Announcements table for system and feature messages
-- Supports displaying different announcements on login vs main app

CREATE TABLE IF NOT EXISTS announcements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type ENUM('system', 'feature') NOT NULL,
    message TEXT NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    display_on ENUM('login', 'app', 'both') DEFAULT 'both',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_active_type (active, type),
    INDEX idx_display_on (display_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Only one active announcement per type should exist at a time
-- This is enforced in application logic
