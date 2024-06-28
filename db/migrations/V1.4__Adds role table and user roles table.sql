-- Create the roles table
CREATE TABLE roles (
    role_id INT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(255) NOT NULL UNIQUE
);

INSERT INTO roles (role_name) VALUES ('super_admin');
INSERT INTO roles (role_name) VALUES ('org_admin');


-- Create the user_roles table
CREATE TABLE user_roles (
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    PRIMARY KEY (user_id, role_id)
);
