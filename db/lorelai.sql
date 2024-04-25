-- Create a new database
CREATE DATABASE IF NOT EXISTS `lorelai`;
USE `lorelai`;

-- Create the 'organisations' table
CREATE TABLE IF NOT EXISTS `organisations` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(255) UNIQUE,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Create the 'users' table
CREATE TABLE IF NOT EXISTS `users` (
    `user_id` INT NOT NULL AUTO_INCREMENT,
    `org_id` INT,
    `name` VARCHAR(255),
    `email` VARCHAR(255),
    `access_token` TEXT,
    `refresh_token` TEXT,
    `expires_in` INT,
    `token_type` VARCHAR(255),
    `scope` TEXT,
    PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
