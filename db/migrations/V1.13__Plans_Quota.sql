-- V1.13__Plans_Quota.sql


-- Create Plan table
CREATE TABLE plans (
    plan_id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    plan_name VARCHAR(50) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    duration_months INT UNSIGNED NOT NULL,
    message_limit_daily INT UNSIGNED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Init Plan table
INSERT INTO plans (plan_name, price, duration_months, message_limit_daily) VALUES
('free', 0.00, 1, 100),
('plus', 10.99, 1, 500),
('pro', 20.99, 1, 1000);

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

-- Create Extra Messages table
CREATE TABLE extra_messages (
    user_id INT PRIMARY KEY,
    quantity INT UNSIGNED NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE
);

CREATE TABLE user_message_usage (
    user_id INT PRIMARY KEY,
    message_count INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES `user`(user_id)
);

-- Add indexes for better query performance
CREATE INDEX idx_user_plans_user_id ON user_plans(user_id);
CREATE INDEX idx_user_plans_plan_id ON user_plans(plan_id);
CREATE INDEX idx_extra_messages_user_id ON extra_messages(user_id);
