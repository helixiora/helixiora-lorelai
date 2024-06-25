-- Version: 1.3
-- Description: Alter usertable
-- Migration script for altering the users table

-- Rename the users.name field to users.user_name
ALTER TABLE users CHANGE COLUMN name user_name varchar(255) NOT NULL;

--Add a new column full_name to the users table
ALTER TABLE users ADD COLUMN full_name varchar(255) NOT NULL;
ALTER TABLE users ADD COLUMN google_id varchar(255) NOT NULL;
UPDATE users SET full_name = user_name;
