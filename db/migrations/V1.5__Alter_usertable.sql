-- Version: 1.5
-- Description: Alter usertable
-- Migration script for altering the users table

-- Rename the users.name field to users.user_name
ALTER TABLE users CHANGE COLUMN name user_name VARCHAR(255) NOT NULL;

-- Add a new column full_name to the users table
ALTER TABLE users ADD COLUMN full_name VARCHAR(255) NOT NULL;

-- Add a new column google_id to the users table
ALTER TABLE users ADD COLUMN google_id VARCHAR(255) NOT NULL;

-- Update full_name with the values from user_name
UPDATE users SET full_name = user_name;
