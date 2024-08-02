CREATE TABLE google_drive_items (
    id int PRIMARY KEY AUTO_INCREMENT,
    user_id int NOT NULL,
    google_drive_id VARCHAR(255) NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(255) NOT NULL,
    item_type VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_indexed_at TIMESTAMP
);
