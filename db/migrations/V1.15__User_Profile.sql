-- V1.15__User_Profile.sql

CREATE TABLE user_profile (
    profile_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    bio TEXT NULL,
    location VARCHAR(255) NULL,
    birth_date DATE NULL,
    avatar_url VARCHAR(255) NULL,
    FOREIGN KEY (user_id) REFERENCES user(user_id)
);
