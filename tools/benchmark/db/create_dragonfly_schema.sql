-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS `dragonfly`;
USE `dragonfly`;

-- Create the tables

-- Benchmark table
CREATE TABLE IF NOT EXISTS `benchmark` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Benchmark metadata table
CREATE TABLE IF NOT EXISTS `benchmark_metadata` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `benchmark_id` INT NOT NULL,
    `key` VARCHAR(255) NOT NULL,
    `value` TEXT,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`benchmark_id`) REFERENCES `benchmark`(`id`) ON DELETE CASCADE
);

-- Benchmark run table
CREATE TABLE IF NOT EXISTS `benchmark_run` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `benchmark_id` INT NOT NULL,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`benchmark_id`) REFERENCES `benchmark`(`id`) ON DELETE CASCADE
);

-- Benchmark run results table
CREATE TABLE IF NOT EXISTS `benchmark_run_result` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `benchmark_run_id` INT NOT NULL,
    `key` VARCHAR(255) NOT NULL,
    `value` TEXT,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`benchmark_run_id`) REFERENCES `benchmark_run`(`id`) ON DELETE CASCADE
);
