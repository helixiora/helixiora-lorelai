-- Insert 'Slack' datasource if it does not exist
INSERT IGNORE INTO datasource (datasource_name, datasource_type) VALUES ('Slack', 'oauth2');
