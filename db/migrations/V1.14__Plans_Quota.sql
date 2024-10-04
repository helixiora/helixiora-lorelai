-- V1.14__Plans_Quota.sql


-- Create Plan table
CREATE TABLE plans (
    plan_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    plan_name VARCHAR(50) NOT NULL,
    description TEXT,
    message_limit_daily INT UNSIGNED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Init Plan table
INSERT INTO plans (plan_name, message_limit_daily) VALUES
('free', 100),
('plus', 500),
('pro', 1000);

-- Create User-Plan association table
CREATE TABLE user_plans (
    user_plan_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    plan_id INT UNSIGNED NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id) ON DELETE CASCADE
);

ALTER TABLE chat_threads
ADD COLUMN marked_deleted BOOLEAN DEFAULT FALSE;

-- Add indexes for better query performance
CREATE INDEX idx_user_plans_user_id ON user_plans(user_id);
CREATE INDEX idx_user_plans_plan_id ON user_plans(plan_id);

-- Give all existing users the free plan
INSERT INTO user_plans (user_id, plan_id, start_date, end_date)
SELECT user_id, 1, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 12 MONTH)
FROM user;
