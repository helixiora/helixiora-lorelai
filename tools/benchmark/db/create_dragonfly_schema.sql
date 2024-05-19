-- Create the database if it doesn't exist
CREATE DATABASE IF NOT EXISTS `dragonfly`;
USE `dragonfly`;

-- Create the tables

-- Benchmark table
CREATE TABLE IF NOT EXISTS `benchmark_template` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
-- Benchmark parameter table
CREATE TABLE IF NOT EXISTS `benchmark_template_parameter` (
    `benchmark_template_id` INT NOT NULL,
    `parameter` VARCHAR(255) NOT NULL,
    `type` VARCHAR(255) NOT NULL,
    `value` TEXT,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    primary key (benchmark_template_id, parameter)
);


-- Benchmark run table
CREATE TABLE IF NOT EXISTS `benchmark_run` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `benchmark_template_id` INT NOT NULL,
    `name` VARCHAR(255) NOT NULL,
    `description` TEXT,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Benchmark run results table
CREATE TABLE IF NOT EXISTS `benchmark_run_result` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `benchmark_run_id` INT NOT NULL,
    `key` VARCHAR(255) NOT NULL,
    `value` TEXT,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
