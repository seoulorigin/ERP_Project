CREATE DATABASE IF NOT EXISTS classdb;
USE classdb;

CREATE TABLE IF NOT EXISTS employees (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    position VARCHAR(100) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 테스트용 직원 데이터 (Requester, Approver)
INSERT INTO employees (name, department, position) VALUES ('Requester', 'Sales', 'Staff');
INSERT INTO employees (name, department, position) VALUES ('Approver', 'Management', 'Manager');