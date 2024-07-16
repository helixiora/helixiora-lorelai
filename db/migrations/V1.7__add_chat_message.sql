CREATE TABLE chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    user_text TEXT NOT NULL,
    bot_text TEXT NOT NULL,
    llm_model VARCHAR(255) NOT NULL,
    source VARCHAR(255) NOT NULL,
    datasource VARCHAR(255) NOT NULL,
    datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (sender_id),
    INDEX (datetime)
);
