CREATE DATABASE IF NOT EXISTS ecommerce_bi CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ecommerce_bi;

DROP VIEW IF EXISTS v_order_lines;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id   VARCHAR(20) PRIMARY KEY,
    customer_name VARCHAR(100),
    email         VARCHAR(150),
    region        VARCHAR(50),
    state         VARCHAR(50),
    signup_date   DATE
);

CREATE TABLE products (
    product_id   VARCHAR(20) PRIMARY KEY,
    product_name VARCHAR(150),
    category     VARCHAR(50),
    unit_cost    DECIMAL(10,2),
    unit_price   DECIMAL(10,2)
);

CREATE TABLE orders (
    order_id     VARCHAR(20) PRIMARY KEY,
    customer_id  VARCHAR(20) NOT NULL,
    order_date   DATETIME NOT NULL,
    order_status VARCHAR(20),
    region       VARCHAR(50),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    INDEX idx_orders_date (order_date),
    INDEX idx_orders_customer (customer_id)
);

CREATE TABLE order_items (
    item_id    INT AUTO_INCREMENT PRIMARY KEY,
    order_id   VARCHAR(20) NOT NULL,
    product_id VARCHAR(20) NOT NULL,
    quantity   INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    discount   DECIMAL(10,2) DEFAULT 0,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    INDEX idx_items_order (order_id)
);

CREATE TABLE payments (
    payment_id     INT PRIMARY KEY,
    order_id       VARCHAR(20) NOT NULL,
    payment_method VARCHAR(30),
    amount         DECIMAL(12,2),
    payment_date   DATETIME,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

CREATE VIEW v_order_lines AS
SELECT oi.order_id,
       o.customer_id,
       o.order_date,
       DATE_FORMAT(o.order_date, '%Y-%m') AS order_month,
       o.order_status,
       o.region,
       p.category,
       p.product_name,
       oi.quantity,
       (oi.quantity * oi.unit_price - oi.discount) AS net_sales,
       (oi.quantity * (oi.unit_price - p.unit_cost) - oi.discount) AS profit,
       CASE WHEN o.order_status IN ('Delivered', 'Shipped') THEN 1 ELSE 0 END AS is_revenue
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id;