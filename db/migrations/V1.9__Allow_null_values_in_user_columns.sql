-- V1.9__Allow_null_values_in_user_columns.sql
ALTER TABLE user
MODIFY user_name VARCHAR(255) NULL,
MODIFY full_name VARCHAR(255) NULL,
MODIFY google_id VARCHAR(255) NULL;
