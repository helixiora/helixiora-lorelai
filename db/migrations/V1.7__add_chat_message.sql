CREATE TABLE chat_threads (
    thread_id VARCHAR(50) PRIMARY KEY,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    thread_name VARCHAR(255),
    UNIQUE KEY unique_thread_id (thread_id)
);

CREATE TABLE chat_messages (
    message_id INT AUTO_INCREMENT PRIMARY KEY,
    thread_id VARCHAR(50) NOT NULL,
    sender ENUM('bot', 'user') NOT NULL,
    message_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sources JSON,
    FOREIGN KEY (thread_id) REFERENCES chat_threads(thread_id)
);
