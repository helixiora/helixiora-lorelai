-- Version: 1.6
-- Description: Move user auth

-- Check if the 'datasource' table exists and create it if it does not
CREATE TABLE IF NOT EXISTS datasource (
  datasource_id INT NOT NULL AUTO_INCREMENT,
  datasource_name VARCHAR(255) NOT NULL,
  datasource_type VARCHAR(255) NOT NULL,
  PRIMARY KEY (datasource_id),
  UNIQUE KEY datasource_name (datasource_name)
);

-- Insert 'Google Drive' datasource if it does not exist
INSERT IGNORE INTO datasource (datasource_name, datasource_type) VALUES ('Google', 'oauth2');

-- Insert 'Slack' datasource if it does not exist
INSERT IGNORE INTO datasource (datasource_name, datasource_type) VALUES ('Slack', 'oauth2');

-- Check if the 'user_auth' table exists and create it if it does not
CREATE TABLE IF NOT EXISTS user_auth (
  user_auth_id INT NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  datasource_id INT NOT NULL,
  auth_key VARCHAR(255) NOT NULL,
  auth_value TEXT NOT NULL,
  auth_type VARCHAR(255) NOT NULL,
  PRIMARY KEY (user_auth_id),
  UNIQUE KEY user_id_datasource_id_key (user_id, datasource_id, auth_key)
);

-- Move user auth data from the 'user' table to the 'user_auth' table, ensuring no duplicates
INSERT IGNORE INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'access_token', access_token, 'oauth2' FROM users WHERE access_token IS NOT NULL;

INSERT IGNORE INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'refresh_token', refresh_token, 'oauth2' FROM users WHERE refresh_token IS NOT NULL;

INSERT IGNORE INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'expiry', expiry, 'oauth2' FROM users WHERE expiry IS NOT NULL;

INSERT IGNORE INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'token_type', token_type, 'oauth2' FROM users WHERE token_type IS NOT NULL;

INSERT IGNORE INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'scope', scope, 'oauth2' FROM users WHERE scope IS NOT NULL;

-- Drop columns from 'user' table if they exist
ALTER TABLE users DROP COLUMN access_token;
ALTER TABLE users DROP COLUMN refresh_token;
ALTER TABLE users DROP COLUMN expiry;
ALTER TABLE users DROP COLUMN token_type;
ALTER TABLE users DROP COLUMN scope;

-- Rename tables only if they exist
RENAME TABLE users TO user;
RENAME TABLE organisations TO organisation;
