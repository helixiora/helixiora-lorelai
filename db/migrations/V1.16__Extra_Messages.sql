-- V1.16__Extra_Messages.sql

CREATE TABLE `extra_messages` (
  `user_id` INT NOT NULL,
  `quantity` INT UNSIGNED NOT NULL,
  `is_active` TINYINT(1) DEFAULT '1',
  `created_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  KEY `idx_extra_messages_user_id` (`user_id`),
  CONSTRAINT `extra_messages_ibfk_1` FOREIGN KEY (`user_id`)
    REFERENCES `user` (`user_id`)
    ON DELETE CASCADE
);
