-- Version: 1.4
-- Description: Move user auth

-- Move the user auth fields to a new table

-- create datasources table
CREATE TABLE datasources (
  datasource_id int NOT NULL AUTO_INCREMENT,
  datasource_name varchar(255) NOT NULL,
  datasource_type varchar(255) NOT NULL,
  PRIMARY KEY (datasource_id),
  UNIQUE KEY datasource_name (datasource_name)
);

-- Google Drive is an oauth2 datasource
INSERT INTO datasources (datasource_name, datasource_type) VALUES ('Google Drive', 'oauth2');
-- Slack is an oauth2 datasource
INSERT INTO datasources (datasource_name, datasource_type) VALUES ('Slack', 'oauth2');

-- Create the user_auth table
CREATE TABLE user_auth (
  user_auth_id int NOT NULL AUTO_INCREMENT,
  user_id int NOT NULL,
  datasource_id int NOT NULL,
  auth_key varchar(255) NOT NULL,
  auth_value text NOT NULL,
  auth_type varchar(255) NOT NULL,
  PRIMARY KEY (user_auth_id),
  UNIQUE KEY user_id_datasource_id_key (user_id, datasource_id, auth_key)
);

-- Move the user auth data from the users table to the user_auth table
INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'access_token', access_token, 'oauth2' FROM users WHERE access_token IS NOT NULL;

INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'refresh_token', refresh_token, 'oauth2' FROM users WHERE refresh_token IS NOT NULL;

INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'expiry', expiry, 'oauth2' FROM users WHERE expiry IS NOT NULL;

INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'token_type', token_type, 'oauth2' FROM users WHERE token_type IS NOT NULL;

INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
SELECT user_id, 1, 'scope', scope, 'oauth2' FROM users WHERE scope IS NOT NULL;

-- Drop the access_token, refresh_token, expires_in, token_type, and scope columns from the users table
ALTER TABLE users DROP COLUMN access_token;
ALTER TABLE users DROP COLUMN refresh_token;
ALTER TABLE users DROP COLUMN expiry;
ALTER TABLE users DROP COLUMN token_type;
ALTER TABLE users DROP COLUMN scope;

-- Rename tables with plural names to singular names
RENAME TABLE datasources TO datasource;
RENAME TABLE users TO user;
RENAME table organisations TO organisation;
