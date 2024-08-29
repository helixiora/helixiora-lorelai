-- V1.11__Update_user_table.sql

-- Drop the slack_token column
ALTER TABLE user
DROP COLUMN slack_token;

-- Add the signup_date column
ALTER TABLE user
ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Create a new table 'user_login' to track user logins
CREATE TABLE user_login (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    login_type VARCHAR(50) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(user_id)
);
