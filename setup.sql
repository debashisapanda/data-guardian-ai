-- =============================================================================
-- DataGuardian AI - Complete Setup Script
-- =============================================================================
-- This script creates the DATA_GUARDIAN_DB database with:
--   1. DEMO_DATA schema  - 5,000+ customers, 20,000+ orders, 500+ products
--   2. QUALITY_ENGINE schema - scan results, rules, health score history
--   3. APP schema - reserved for Streamlit app objects
--
-- Intentional data quality issues are injected for the demo:
--   - NULL values, duplicates, invalid emails, negative prices
--   - Future dates, whitespace, case inconsistencies, orphan keys
--   - Referential integrity violations, outlier values
--
-- Prerequisites:
--   - A role with CREATE DATABASE privilege (e.g., ACCOUNTADMIN or SYSADMIN)
--   - A warehouse to run the script
--
-- Usage:
--   Execute this entire script in a Snowflake worksheet or via SnowSQL.
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- ============================================================
-- 1. DATABASE & SCHEMAS
-- ============================================================

CREATE DATABASE IF NOT EXISTS DATA_GUARDIAN_DB;

CREATE SCHEMA IF NOT EXISTS DATA_GUARDIAN_DB.DEMO_DATA
  COMMENT = 'Demo dataset with intentional quality issues';

CREATE SCHEMA IF NOT EXISTS DATA_GUARDIAN_DB.QUALITY_ENGINE
  COMMENT = 'Data quality framework - rules, scores, audit';

CREATE SCHEMA IF NOT EXISTS DATA_GUARDIAN_DB.APP
  COMMENT = 'Streamlit application objects';


-- ============================================================
-- 2. DEMO DATA TABLES
-- ============================================================

USE SCHEMA DATA_GUARDIAN_DB.DEMO_DATA;

-- ----- CUSTOMERS -----
CREATE OR REPLACE TABLE CUSTOMERS (
    CUSTOMER_ID    NUMBER(38,0),
    FIRST_NAME     VARCHAR(100),
    LAST_NAME      VARCHAR(100),
    EMAIL          VARCHAR(200),
    PHONE          VARCHAR(50),
    ADDRESS        VARCHAR(300),
    CITY           VARCHAR(100),
    STATE          VARCHAR(50),
    COUNTRY        VARCHAR(50),
    POSTAL_CODE    VARCHAR(20),
    DATE_OF_BIRTH  DATE,
    REGISTRATION_DATE TIMESTAMP_NTZ(9),
    CUSTOMER_SEGMENT  VARCHAR(50),
    CREDIT_SCORE   NUMBER(38,0),
    ANNUAL_INCOME  NUMBER(15,2),
    IS_ACTIVE      BOOLEAN,
    LAST_LOGIN     TIMESTAMP_NTZ(9)
);

-- ----- PRODUCTS -----
CREATE OR REPLACE TABLE PRODUCTS (
    PRODUCT_ID     NUMBER(38,0),
    PRODUCT_NAME   VARCHAR(200),
    CATEGORY       VARCHAR(100),
    SUB_CATEGORY   VARCHAR(100),
    BRAND          VARCHAR(100),
    UNIT_PRICE     NUMBER(10,2),
    COST_PRICE     NUMBER(10,2),
    STOCK_QUANTITY NUMBER(38,0),
    REORDER_LEVEL  NUMBER(38,0),
    WEIGHT_KG      NUMBER(8,3),
    IS_ACTIVE      BOOLEAN,
    CREATED_DATE   DATE,
    LAST_UPDATED   TIMESTAMP_NTZ(9)
);

-- ----- ORDERS -----
CREATE OR REPLACE TABLE ORDERS (
    ORDER_ID       NUMBER(38,0),
    CUSTOMER_ID    NUMBER(38,0),
    PRODUCT_ID     NUMBER(38,0),
    ORDER_DATE     TIMESTAMP_NTZ(9),
    DELIVERY_DATE  TIMESTAMP_NTZ(9),
    QUANTITY       NUMBER(38,0),
    UNIT_PRICE     NUMBER(10,2),
    TOTAL_AMOUNT   NUMBER(12,2),
    DISCOUNT_PCT   NUMBER(5,2),
    PAYMENT_METHOD VARCHAR(50),
    ORDER_STATUS   VARCHAR(50),
    SHIPPING_ADDRESS VARCHAR(300),
    CITY           VARCHAR(100),
    STATE          VARCHAR(50),
    COUNTRY        VARCHAR(50)
);


-- ============================================================
-- 3. GENERATE CLEAN BASE DATA (5,000 customers, 500 products, 20,000 orders)
-- ============================================================

-- 3a. 5,000 clean customers
INSERT INTO CUSTOMERS
WITH first_names AS (
    SELECT column1 AS name, column2 AS idx FROM (VALUES
        ('Rahul',1),('Priya',2),('Amit',3),('Sneha',4),('Vikram',5),
        ('Anita',6),('Rajesh',7),('Kavita',8),('Suresh',9),('Deepa',10),
        ('Manoj',11),('Neha',12),('Arun',13),('Pooja',14),('Ravi',15),
        ('Meera',16),('Sanjay',17),('Ritu',18),('Gaurav',19),('Swati',20)
    )
),
last_names AS (
    SELECT column1 AS name, column2 AS idx FROM (VALUES
        ('Sharma',1),('Patel',2),('Singh',3),('Kumar',4),('Gupta',5),
        ('Reddy',6),('Nair',7),('Joshi',8),('Mehta',9),('Rao',10),
        ('Das',11),('Iyer',12),('Chopra',13),('Pillai',14),('Verma',15)
    )
),
domains AS (
    SELECT column1 AS dom, column2 AS idx FROM (VALUES
        ('gmail.com',1),('outlook.com',2),('yahoo.com',3),
        ('company.co.in',4),('hotmail.com',5)
    )
),
cities AS (
    SELECT column1 AS city, column2 AS st, column3 AS idx FROM (VALUES
        ('Mumbai','Maharashtra',1),('Delhi','Delhi',2),('Bangalore','Karnataka',3),
        ('Chennai','Tamil Nadu',4),('Hyderabad','Telangana',5),('Pune','Maharashtra',6),
        ('Kolkata','West Bengal',7),('Ahmedabad','Gujarat',8)
    )
),
streets AS (
    SELECT column1 AS street, column2 AS idx FROM (VALUES
        ('MG Road',1),('Park Street',2),('Brigade Road',3),
        ('Marine Drive',4),('Connaught Place',5)
    )
),
segments AS (
    SELECT column1 AS seg, column2 AS idx FROM (VALUES
        ('Premium',1),('Standard',2),('Basic',3),('Enterprise',4)
    )
),
seq AS (
    SELECT SEQ4()+1 AS id FROM TABLE(GENERATOR(ROWCOUNT => 5000))
)
SELECT
    s.id AS CUSTOMER_ID,
    fn.name AS FIRST_NAME,
    ln.name AS LAST_NAME,
    LOWER(fn.name) || '.' || LOWER(ln.name) || s.id || '@' || d.dom AS EMAIL,
    '+91-7' || LPAD(ABS(HASH(s.id)) % 1000000000, 9, '0') AS PHONE,
    s.id || ' ' || st.street AS ADDRESS,
    c.city AS CITY,
    c.st AS STATE,
    'India' AS COUNTRY,
    '400' || LPAD(MOD(s.id, 300) + 1, 3, '0') AS POSTAL_CODE,
    DATEADD(day, -(MOD(ABS(HASH(s.id + 100)), 25000) + 6000), CURRENT_DATE()) AS DATE_OF_BIRTH,
    DATEADD(day, -(MOD(ABS(HASH(s.id + 200)), 2000)), CURRENT_TIMESTAMP()) AS REGISTRATION_DATE,
    seg.seg AS CUSTOMER_SEGMENT,
    300 + MOD(ABS(HASH(s.id + 300)), 551) AS CREDIT_SCORE,
    ROUND(100000 + MOD(ABS(HASH(s.id + 42)), 4900000), 2) AS ANNUAL_INCOME,
    TRUE AS IS_ACTIVE,
    DATEADD(day, -(MOD(ABS(HASH(s.id + 400)), 30)), CURRENT_TIMESTAMP()) AS LAST_LOGIN
FROM seq s
JOIN first_names fn ON fn.idx = MOD(s.id - 1, 20) + 1
JOIN last_names  ln ON ln.idx = MOD(FLOOR((s.id - 1) / 20), 15) + 1
JOIN domains     d  ON d.idx  = MOD(s.id - 1, 5) + 1
JOIN cities      c  ON c.idx  = MOD(s.id - 1, 8) + 1
JOIN streets     st ON st.idx = MOD(s.id - 1, 5) + 1
JOIN segments   seg ON seg.idx = MOD(s.id - 1, 4) + 1;

-- 3b. 500 clean products
INSERT INTO PRODUCTS
WITH categories AS (
    SELECT column1 AS cat, column2 AS sub, column3 AS idx FROM (VALUES
        ('Electronics','Phones',1),('Electronics','Laptops',2),('Electronics','Tablets',3),
        ('Clothing','Shirts',4),('Clothing','Pants',5),('Clothing','Shoes',6),
        ('Food & Beverage','Snacks',7),('Food & Beverage','Drinks',8),
        ('Home & Garden','Furniture',9),('Home & Garden','Kitchen',10),
        ('Sports','Cricket',11),('Sports','Fitness',12),
        ('Books','Fiction',13),('Books','Non-Fiction',14),
        ('Beauty','Skincare',15)
    )
),
brands AS (
    SELECT column1 AS brand, column2 AS idx FROM (VALUES
        ('BrandA',1),('BrandB',2),('BrandC',3),('BrandD',4),('BrandE',5)
    )
),
seq AS (
    SELECT SEQ4()+1 AS id FROM TABLE(GENERATOR(ROWCOUNT => 500))
)
SELECT
    s.id AS PRODUCT_ID,
    'Product_' || s.id AS PRODUCT_NAME,
    c.cat AS CATEGORY,
    c.sub AS SUB_CATEGORY,
    b.brand AS BRAND,
    ROUND(50 + MOD(ABS(HASH(s.id + 100)), 9950), 2) AS UNIT_PRICE,
    ROUND(25 + MOD(ABS(HASH(s.id + 200)), 4975), 2) AS COST_PRICE,
    10 + MOD(ABS(HASH(s.id + 500)), 491) AS STOCK_QUANTITY,
    5  + MOD(ABS(HASH(s.id + 600)), 46)  AS REORDER_LEVEL,
    ROUND(0.1 + MOD(ABS(HASH(s.id + 300)), 2990) / 100.0, 3) AS WEIGHT_KG,
    TRUE AS IS_ACTIVE,
    DATEADD(day, -(MOD(ABS(HASH(s.id + 700)), 900) + 30), CURRENT_DATE()) AS CREATED_DATE,
    CURRENT_TIMESTAMP() AS LAST_UPDATED
FROM seq s
JOIN categories c ON c.idx = MOD(s.id - 1, 15) + 1
JOIN brands     b ON b.idx = MOD(s.id - 1, 5) + 1;

-- 3c. 20,000 clean orders
INSERT INTO ORDERS
WITH payment_methods AS (
    SELECT column1 AS pm, column2 AS idx FROM (VALUES
        ('Credit Card',1),('Debit Card',2),('UPI',3),
        ('Net Banking',4),('Cash on Delivery',5)
    )
),
statuses AS (
    SELECT column1 AS st, column2 AS idx FROM (VALUES
        ('Processing',1),('Shipped',2),('Delivered',3),
        ('Returned',4),('Cancelled',5)
    )
),
seq AS (
    SELECT SEQ4()+1 AS id FROM TABLE(GENERATOR(ROWCOUNT => 20000))
)
SELECT
    s.id AS ORDER_ID,
    1 + MOD(ABS(HASH(s.id)), 5000) AS CUSTOMER_ID,
    1 + MOD(ABS(HASH(s.id + 1000)), 500) AS PRODUCT_ID,
    DATEADD(day, -(MOD(ABS(HASH(s.id + 2000)), 730)), CURRENT_TIMESTAMP()) AS ORDER_DATE,
    DATEADD(day, -(MOD(ABS(HASH(s.id + 2000)), 730)) + 3 + MOD(ABS(HASH(s.id + 3000)), 7), CURRENT_TIMESTAMP()) AS DELIVERY_DATE,
    1 + MOD(ABS(HASH(s.id + 4000)), 10) AS QUANTITY,
    ROUND(50 + MOD(ABS(HASH(s.id + 500)), 9950), 2) AS UNIT_PRICE,
    ROUND((1 + MOD(ABS(HASH(s.id + 4000)), 10)) * (50 + MOD(ABS(HASH(s.id + 500)), 9950)), 2) AS TOTAL_AMOUNT,
    ROUND(MOD(ABS(HASH(s.id + 600)), 2500) / 100.0, 2) AS DISCOUNT_PCT,
    pm.pm AS PAYMENT_METHOD,
    st.st AS ORDER_STATUS,
    (1 + MOD(ABS(HASH(s.id)), 5000)) || ' Main St' AS SHIPPING_ADDRESS,
    CASE MOD(s.id, 6)
        WHEN 0 THEN 'Mumbai' WHEN 1 THEN 'Delhi' WHEN 2 THEN 'Bangalore'
        WHEN 3 THEN 'Chennai' WHEN 4 THEN 'Hyderabad' ELSE 'Pune'
    END AS CITY,
    CASE MOD(s.id, 6)
        WHEN 0 THEN 'Maharashtra' WHEN 1 THEN 'Delhi' WHEN 2 THEN 'Karnataka'
        WHEN 3 THEN 'Tamil Nadu' WHEN 4 THEN 'Telangana' ELSE 'Maharashtra'
    END AS STATE,
    'India' AS COUNTRY
FROM seq s
JOIN payment_methods pm ON pm.idx = MOD(s.id - 1, 5) + 1
JOIN statuses       st ON st.idx = MOD(s.id - 1, 5) + 1;


-- ============================================================
-- 4. INJECT QUALITY ISSUES
-- ============================================================

-- -------- CUSTOMERS: Quality Issues --------

-- 4a. NULL primary keys
INSERT INTO CUSTOMERS VALUES
    (NULL, 'Test', 'User1', 'test1@gmail.com', '+91-9876543210', '1 Main St', 'Mumbai', 'Maharashtra', 'India', '400001', '1990-01-01', CURRENT_TIMESTAMP(), 'Basic', 700, 300000, TRUE, CURRENT_TIMESTAMP()),
    (NULL, 'Test', 'User2', 'test2@gmail.com', '+91-9876543211', '2 Main St', 'Delhi', 'Delhi', 'India', '110001', '1985-05-15', CURRENT_TIMESTAMP(), 'Standard', 650, 400000, TRUE, CURRENT_TIMESTAMP());

-- 4b. Duplicate rows (same ID, different casing = case inconsistency)
INSERT INTO CUSTOMERS VALUES
    (100, 'Rahul', 'Sharma', 'rahul.sharma100@gmail.com', '+91-9988776655', '100 MG Road', 'Mumbai', 'Maharashtra', 'India', '400001', '1988-03-15', '2024-01-15 10:00:00', 'Premium', 800, 2500000, TRUE, CURRENT_TIMESTAMP()),
    (100, 'RAHUL', 'SHARMA', 'RAHUL.SHARMA100@GMAIL.COM', '+91-9988776655', '100 MG Road', 'mumbai', 'maharashtra', 'India', '400001', '1988-03-15', '2024-01-15 10:00:00', 'Premium', 800, 2500000, TRUE, CURRENT_TIMESTAMP()),
    (100, 'rahul', 'sharma', 'rahul.sharma100@gmail.com', '+91-9988776655', '100 MG Road', 'Mumbai', 'Maharashtra', 'India', '400001', '1988-03-15', '2024-01-15 10:00:00', NULL, 800, 2500000, TRUE, CURRENT_TIMESTAMP()),
    (200, 'Priya', 'Patel', 'priya.patel@outlook.com', '+91-8877665544', '50 Park St', 'Bangalore', 'Karnataka', 'India', '560001', '1992-07-22', '2023-06-01 08:30:00', 'Enterprise', 850, 4500000, TRUE, CURRENT_TIMESTAMP()),
    (200, 'Priya', 'Patel', 'priya.patel@outlook.com', '+91-8877665544', '50 Park St', 'Bangalore', 'Karnataka', 'India', '560001', '1992-07-22', '2023-06-01 08:30:00', 'Enterprise', 850, 4500000, TRUE, CURRENT_TIMESTAMP());

-- 4c. Invalid emails
INSERT INTO CUSTOMERS VALUES
    (5001, 'Bad', 'Email1', 'not-an-email', '+91-9999999999', '1 St', 'Mumbai', 'Maharashtra', 'India', '400001', '1990-01-01', CURRENT_TIMESTAMP(), 'Basic', 700, 300000, TRUE, CURRENT_TIMESTAMP()),
    (5002, 'Bad', 'Email2', 'missing@', '+91-9999999998', '2 St', 'Delhi', 'Delhi', 'India', '110001', '1991-02-02', CURRENT_TIMESTAMP(), 'Standard', 650, 400000, TRUE, CURRENT_TIMESTAMP());

-- 4d. NULL emails, phones
INSERT INTO CUSTOMERS VALUES
    (5005, 'Bad', 'Email5', '', '+91-9999999995', '5 St', 'Hyderabad', 'Telangana', 'India', '500001', '1994-05-05', CURRENT_TIMESTAMP(), 'Basic', 680, 280000, TRUE, CURRENT_TIMESTAMP()),
    (5015, 'NoEmail', 'Customer', NULL, '+91-6666666663', '15 St', 'Bangalore', 'Karnataka', 'India', '560001', '1992-01-01', CURRENT_TIMESTAMP(), 'Premium', 750, 500000, TRUE, CURRENT_TIMESTAMP()),
    (5016, 'NoPhone', 'Customer', 'nophone@gmail.com', NULL, '16 St', 'Chennai', 'Tamil Nadu', 'India', '600001', '1993-01-01', CURRENT_TIMESTAMP(), NULL, 700, 300000, TRUE, CURRENT_TIMESTAMP());

-- 4e. Whitespace issues
INSERT INTO CUSTOMERS VALUES
    (5006, '  Rajesh  ', 'Kumar', 'rajesh.k@gmail.com', '+91-8888888881', '6 St', '  Mumbai  ', 'MAHARASHTRA', 'INDIA', '400001', '1985-06-06', CURRENT_TIMESTAMP(), NULL, 720, 380000, TRUE, CURRENT_TIMESTAMP()),
    (5008, ' Suresh', 'Nair ', 'suresh.n@hotmail.com', '+91-8888888883', '8 St', 'chennai ', ' Tamil Nadu', 'India', '600001', '1989-08-08', CURRENT_TIMESTAMP(), 'Standard', 710, 450000, TRUE, CURRENT_TIMESTAMP());

-- 4f. Future DOB, negative income, outlier credit score
INSERT INTO CUSTOMERS VALUES
    (5009, 'Future', 'Person', 'future@gmail.com', '+91-7777777771', '9 St', 'Mumbai', 'Maharashtra', 'India', '400001', '2030-01-01', CURRENT_TIMESTAMP(), 'Premium', 950, -500000, TRUE, CURRENT_TIMESTAMP());

-- 4g. Completely NULL row (ghost record)
INSERT INTO CUSTOMERS VALUES
    (NULL, 'Ghost', 'Record', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO CUSTOMERS VALUES
    (5017, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);


-- -------- PRODUCTS: Quality Issues --------

-- 4h. NULL product name, negative price, zero price, negative stock
INSERT INTO PRODUCTS VALUES
    (NULL, 'No ID Product', 'Electronics', 'Phones', 'BrandA', 999.99, 500.00, 100, 20, 0.500, TRUE, '2024-01-01', CURRENT_TIMESTAMP()),
    (501,   NULL,           'Clothing', 'Shirts', 'BrandB', 499.99, 250.00, 50, 10, 0.300, TRUE, '2024-02-01', CURRENT_TIMESTAMP()),
    (502,  'Negative Price','Food & Beverage', 'Snacks', 'BrandC', -199.99, -100.00, 200, 30, 0.100, TRUE, '2024-03-01', CURRENT_TIMESTAMP()),
    (503,  'Zero Price',    'Electronics', 'Laptops', NULL, 0.00, 0.00, -50, 20, 2.500, TRUE, '2024-04-01', CURRENT_TIMESTAMP()),
    (504,  'Future Product','Sports', 'Cricket', 'BrandD', 1500.00, 800.00, 100, 25, 1.200, TRUE, '2030-06-15', CURRENT_TIMESTAMP()),
    (505,  'Whitespace Product', 'Electronics', 'Phones', 'BrandA', 2999.99, 1500.00, 75, 15, 0.400, TRUE, '2024-05-01', CURRENT_TIMESTAMP()),
    (506,  'Cost > Price',  'Home & Garden', 'Furniture', 'BrandE', 500.00, 800.00, 30, 10, 15.000, TRUE, '2024-06-01', CURRENT_TIMESTAMP()),
    (507,  'Duplicate',     'Books', 'Fiction', 'BrandF', 299.99, 150.00, 200, 40, 0.500, TRUE, '2024-07-01', CURRENT_TIMESTAMP()),
    (507,  'Duplicate',     'Books', 'Fiction', 'BrandF', 299.99, 150.00, 200, 40, 0.500, TRUE, '2024-07-01', CURRENT_TIMESTAMP()),
    (508,  'Invalid Category', NULL, 'UNKNOWN', 'BrandG', 199.99, 100.00, 100, 20, 0.800, TRUE, '2024-08-01', CURRENT_TIMESTAMP());


-- -------- ORDERS: Quality Issues --------

-- 4i. Orphan customer IDs (99901-99905 don't exist in CUSTOMERS)
INSERT INTO ORDERS VALUES
    (20001, 99901, 1,   CURRENT_TIMESTAMP(), DATEADD(day, 5, CURRENT_TIMESTAMP()), 2, 500.00, 1000.00, 0.00, 'UPI', 'Processing', '1 St', 'Mumbai', 'Maharashtra', 'India'),
    (20002, 99902, 2,   CURRENT_TIMESTAMP(), DATEADD(day, 5, CURRENT_TIMESTAMP()), 1, 1500.00, 1500.00, 10.00, 'Credit Card', 'Shipped', '2 St', 'Delhi', 'Delhi', 'India'),
    (20003, 99903, 3,   CURRENT_TIMESTAMP(), DATEADD(day, 5, CURRENT_TIMESTAMP()), 3, 200.00, 600.00, 5.00, 'Net Banking', 'Delivered', '3 St', 'Pune', 'Maharashtra', 'India'),
    (20004, 99904, 501, CURRENT_TIMESTAMP(), DATEADD(day, 7, CURRENT_TIMESTAMP()), 1, 999.99, 999.99, 0.00, 'UPI', 'Processing', '4 St', 'Chennai', 'Tamil Nadu', 'India'),
    (20005, 99905, 502, CURRENT_TIMESTAMP(), DATEADD(day, 3, CURRENT_TIMESTAMP()), 5, 100.00, 500.00, 15.00, 'Cash on Delivery', 'Shipped', '5 St', 'Bangalore', 'Karnataka', 'India');

-- 4j. Negative quantity and amount
INSERT INTO ORDERS VALUES
    (20006, 100, 10, '2024-06-01', '2024-06-05', -3, 500.00, -1500.00, 0.00, 'Credit Card', 'Delivered', '6 St', 'Mumbai', 'Maharashtra', 'India'),
    (20007, 200, 20, '2024-07-01', '2024-07-05', 2, -800.00, -1600.00, 0.00, 'UPI', 'Delivered', '7 St', 'Delhi', 'Delhi', 'India');

-- 4k. Normal orders (more variety)
INSERT INTO ORDERS VALUES
    (20008, 300, 30, '2024-08-01', '2024-08-05', 1, 1000.00, 1000.00, 0.00, 'Net Banking', 'Shipped', '8 St', 'Pune', 'Maharashtra', 'India');

-- 4l. Future-dated orders
INSERT INTO ORDERS VALUES
    (20009, 400, 40, '2030-01-01', '2030-01-15', 2, 2000.00, 4000.00, 5.00, 'Credit Card', 'Delivered', '9 St', 'Chennai', 'Tamil Nadu', 'India'),
    (20010, 500, 50, '2029-06-15', '2029-06-20', 1, 3000.00, 3000.00, 0.00, 'UPI', 'Processing', '10 St', 'Hyderabad', 'Telangana', 'India');

-- 4m. Delivery before order (date ordering issue)
INSERT INTO ORDERS VALUES
    (20011, 600, 60, '2024-09-15', '2024-09-10', 3, 400.00, 1200.00, 0.00, 'Debit Card', 'Delivered', '11 St', 'Mumbai', 'Maharashtra', 'India'),
    (20012, 700, 70, '2024-10-20', '2024-10-15', 1, 5000.00, 5000.00, 10.00, 'Net Banking', 'Delivered', '12 St', 'Bangalore', 'Karnataka', 'India');

-- 4n. NULL order IDs
INSERT INTO ORDERS VALUES
    (NULL, 800, 80, '2024-11-01', '2024-11-05', 2, 600.00, 1200.00, 0.00, 'UPI', 'Shipped', '13 St', 'Delhi', 'Delhi', 'India'),
    (NULL, 900, 90, '2024-12-01', '2024-12-05', 1, 1000.00, 1000.00, 5.00, 'Credit Card', 'Delivered', '14 St', 'Chennai', 'Tamil Nadu', 'India');

-- 4o. NULL status
INSERT INTO ORDERS VALUES
    (20015, 1000, 100, '2024-11-15', '2024-11-20', 2, 750.00, 1500.00, 0.00, 'UPI', NULL, '15 St', 'Pune', 'Maharashtra', 'India'),
    (20016, 1100, 110, '2024-12-15', '2024-12-20', 1, 2500.00, 2500.00, 10.00, 'Credit Card', NULL, '16 St', 'Hyderabad', 'Telangana', 'India');

-- 4p. Duplicate order
INSERT INTO ORDERS VALUES
    (20017, 1200, 120, '2024-10-01', '2024-10-05', 3, 300.00, 900.00, 0.00, 'Cash on Delivery', 'Delivered', '17 St', 'Mumbai', 'Maharashtra', 'India'),
    (20017, 1200, 120, '2024-10-01', '2024-10-05', 3, 300.00, 900.00, 0.00, 'Cash on Delivery', 'Delivered', '17 St', 'Mumbai', 'Maharashtra', 'India');

-- 4q. NULL customer IDs (referential integrity)
INSERT INTO ORDERS VALUES
    (20019, NULL, 130, '2024-09-01', '2024-09-05', 2, 800.00, 1600.00, 5.00, 'UPI', 'Shipped', '19 St', 'Delhi', 'Delhi', 'India'),
    (20020, NULL, 140, '2024-08-01', '2024-08-05', 1, 1200.00, 1200.00, 0.00, 'Net Banking', 'Delivered', '20 St', 'Bangalore', 'Karnataka', 'India');

-- 4r. More normal orders
INSERT INTO ORDERS VALUES
    (20021, 1300, 150, '2024-07-15', '2024-07-20', 5, 200.00, 1000.00, 0.00, 'Debit Card', 'Delivered', '21 St', 'Chennai', 'Tamil Nadu', 'India'),
    (20022, 1400, 160, '2024-06-15', '2024-06-20', 2, 1000.00, 2000.00, 0.00, 'Credit Card', 'Delivered', '22 St', 'Mumbai', 'Maharashtra', 'India');


-- ============================================================
-- 5. QUALITY ENGINE TABLES
-- ============================================================

USE SCHEMA DATA_GUARDIAN_DB.QUALITY_ENGINE;

-- ----- SCAN_RESULTS -----
CREATE OR REPLACE TABLE SCAN_RESULTS (
    SCAN_ID              VARCHAR(50),
    SCAN_TIMESTAMP       TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    DATABASE_NAME        VARCHAR(200),
    SCHEMA_NAME          VARCHAR(200),
    TABLE_NAME           VARCHAR(200),
    TOTAL_ROWS           NUMBER(38,0),
    TOTAL_COLUMNS        NUMBER(38,0),
    ISSUES_FOUND         NUMBER(38,0),
    CRITICAL_ISSUES      NUMBER(38,0),
    HIGH_ISSUES          NUMBER(38,0),
    MEDIUM_ISSUES        NUMBER(38,0),
    LOW_ISSUES           NUMBER(38,0),
    HEALTH_SCORE         NUMBER(5,2),
    COMPLETENESS_SCORE   NUMBER(5,2),
    UNIQUENESS_SCORE     NUMBER(5,2),
    VALIDITY_SCORE       NUMBER(5,2),
    CONSISTENCY_SCORE    NUMBER(5,2),
    INTEGRITY_SCORE      NUMBER(5,2),
    FRESHNESS_SCORE      NUMBER(5,2),
    SCAN_DURATION_SECONDS NUMBER(10,2),
    SCAN_TYPE            VARCHAR(20) DEFAULT 'DEEP'
);

-- ----- SCAN_ISSUES -----
CREATE OR REPLACE TABLE SCAN_ISSUES (
    ISSUE_ID             VARCHAR(50),
    SCAN_ID              VARCHAR(50),
    TABLE_NAME           VARCHAR(200),
    COLUMN_NAME          VARCHAR(200),
    RULE_CATEGORY        VARCHAR(50),
    RULE_NAME            VARCHAR(200),
    SEVERITY             VARCHAR(20),
    AFFECTED_ROWS        NUMBER(38,0),
    TOTAL_ROWS           NUMBER(38,0),
    AFFECTED_PERCENTAGE  NUMBER(7,4),
    ISSUE_DESCRIPTION    VARCHAR(1000),
    BUSINESS_IMPACT      VARCHAR(1000),
    RECOMMENDED_ACTION   VARCHAR(1000),
    REMEDIATION_SQL      VARCHAR(5000),
    RISK_LEVEL           VARCHAR(20),
    CONFIDENCE_LEVEL     NUMBER(5,2),
    DETECTED_AT          TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP()
);

-- ----- QUALITY_RULES -----
CREATE OR REPLACE TABLE QUALITY_RULES (
    RULE_ID              NUMBER(38,0) AUTOINCREMENT START 1 INCREMENT 1,
    RULE_NAME            VARCHAR(200),
    RULE_CATEGORY        VARCHAR(50),
    RULE_DESCRIPTION     VARCHAR(500),
    APPLICABLE_DATA_TYPES VARCHAR(200),
    SEVERITY_DEFAULT     VARCHAR(20),
    IS_ACTIVE            BOOLEAN DEFAULT TRUE,
    CREATED_AT           TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP()
);

INSERT INTO QUALITY_RULES (RULE_NAME, RULE_CATEGORY, RULE_DESCRIPTION, APPLICABLE_DATA_TYPES, SEVERITY_DEFAULT) VALUES
    ('NULL_CHECK',             'COMPLETENESS',  'Check for NULL values in columns',                         'NUMBER,VARCHAR,DATE,TIMESTAMP,BOOLEAN', 'HIGH'),
    ('BLANK_STRING_CHECK',     'COMPLETENESS',  'Check for empty or blank string values',                   'VARCHAR',                               'MEDIUM'),
    ('DUPLICATE_CHECK',        'UNIQUENESS',    'Check for duplicate values in key columns',                'NUMBER,VARCHAR',                        'CRITICAL'),
    ('DUPLICATE_ROW_CHECK',    'UNIQUENESS',    'Check for completely duplicate rows',                      'NUMBER,VARCHAR,DATE,TIMESTAMP,BOOLEAN', 'CRITICAL'),
    ('EMAIL_FORMAT',           'VALIDITY',      'Validate email address format',                            'VARCHAR',                               'HIGH'),
    ('PHONE_FORMAT',           'VALIDITY',      'Validate phone number format',                             'VARCHAR',                               'MEDIUM'),
    ('DATE_RANGE',             'VALIDITY',      'Check for impossible or future dates',                     'DATE,TIMESTAMP',                        'HIGH'),
    ('NUMERIC_RANGE',          'VALIDITY',      'Check for negative or out-of-range numeric values',        'NUMBER',                                'HIGH'),
    ('CATEGORICAL_VALIDITY',   'VALIDITY',      'Check values against expected categories',                 'VARCHAR',                               'MEDIUM'),
    ('WHITESPACE_CHECK',       'CONSISTENCY',   'Check for leading/trailing whitespace',                    'VARCHAR',                               'LOW'),
    ('CASE_CONSISTENCY',       'CONSISTENCY',   'Check for inconsistent casing in categorical columns',     'VARCHAR',                               'LOW'),
    ('REFERENTIAL_INTEGRITY',  'INTEGRITY',     'Check foreign key relationships',                          'NUMBER',                                'CRITICAL'),
    ('AMOUNT_CONSISTENCY',     'VALIDITY',      'Check quantity * price = total_amount',                    'NUMBER',                                'HIGH'),
    ('DATE_ORDERING',          'VALIDITY',      'Check that date sequences are logical (e.g., delivery after order)', 'DATE,TIMESTAMP',              'HIGH'),
    ('FRESHNESS_CHECK',        'FRESHNESS',     'Check if data has been recently updated',                  'TIMESTAMP',                             'MEDIUM'),
    ('OUTLIER_DETECTION',      'ACCURACY',      'Statistical outlier detection using IQR',                  'NUMBER',                                'MEDIUM');

-- ----- REMEDIATION_LOG -----
CREATE OR REPLACE TABLE REMEDIATION_LOG (
    REMEDIATION_ID       VARCHAR(50),
    SCAN_ID              VARCHAR(50),
    ISSUE_ID             VARCHAR(50),
    TABLE_NAME           VARCHAR(200),
    COLUMN_NAME          VARCHAR(200),
    ISSUE_TYPE           VARCHAR(200),
    SEVERITY             VARCHAR(20),
    AFFECTED_ROWS        NUMBER(38,0),
    REMEDIATION_SQL      VARCHAR(5000),
    APPROVAL_STATUS      VARCHAR(20) DEFAULT 'PENDING',
    APPROVED_BY          VARCHAR(200),
    APPROVED_AT          TIMESTAMP_NTZ(9),
    EXECUTED_AT          TIMESTAMP_NTZ(9),
    EXECUTION_RESULT     VARCHAR(1000),
    BEFORE_SCORE         NUMBER(5,2),
    AFTER_SCORE          NUMBER(5,2),
    CREATED_AT           TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP()
);

-- ----- QUALITY_CONTRACTS -----
CREATE OR REPLACE TABLE QUALITY_CONTRACTS (
    CONTRACT_ID          NUMBER(38,0) AUTOINCREMENT START 1 INCREMENT 1,
    CONTRACT_NAME        VARCHAR(200),
    TABLE_NAME           VARCHAR(200),
    COLUMN_NAME          VARCHAR(200),
    NATURAL_LANGUAGE_RULE VARCHAR(500),
    GENERATED_SQL_CHECK  VARCHAR(2000),
    SEVERITY             VARCHAR(20) DEFAULT 'HIGH',
    IS_ACTIVE            BOOLEAN DEFAULT TRUE,
    CREATED_BY           VARCHAR(200) DEFAULT CURRENT_USER(),
    CREATED_AT           TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP()
);

-- ----- HEALTH_SCORE_HISTORY -----
CREATE OR REPLACE TABLE HEALTH_SCORE_HISTORY (
    RECORD_ID            NUMBER(38,0) AUTOINCREMENT START 1 INCREMENT 1,
    SCAN_ID              VARCHAR(50),
    SCAN_DATE            DATE,
    DATABASE_NAME        VARCHAR(200),
    SCHEMA_NAME          VARCHAR(200),
    TABLE_NAME           VARCHAR(200),
    HEALTH_SCORE         NUMBER(5,2),
    COMPLETENESS_SCORE   NUMBER(5,2),
    UNIQUENESS_SCORE     NUMBER(5,2),
    VALIDITY_SCORE       NUMBER(5,2),
    CONSISTENCY_SCORE    NUMBER(5,2),
    INTEGRITY_SCORE      NUMBER(5,2),
    FRESHNESS_SCORE      NUMBER(5,2),
    TOTAL_ISSUES         NUMBER(38,0),
    CRITICAL_ISSUES      NUMBER(38,0),
    ROWS_AT_RISK         NUMBER(38,0),
    RECORDED_AT          TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP()
);

-- ----- SCORE_WEIGHTS -----
CREATE OR REPLACE TABLE SCORE_WEIGHTS (
    DIMENSION   VARCHAR(50),
    WEIGHT      NUMBER(5,2),
    DESCRIPTION VARCHAR(200)
);

INSERT INTO SCORE_WEIGHTS VALUES
    ('COMPLETENESS', 0.25, 'How complete is the data - missing/null values'),
    ('UNIQUENESS',   0.20, 'Are there duplicate records or values'),
    ('VALIDITY',     0.20, 'Do values conform to expected formats and ranges'),
    ('CONSISTENCY',  0.15, 'Are values consistent in format and casing'),
    ('INTEGRITY',    0.15, 'Do referential relationships hold'),
    ('FRESHNESS',    0.05, 'Is the data up to date');


-- ============================================================
-- 6. SEED HEALTH SCORE HISTORY (6-day trend for dashboard)
-- ============================================================

INSERT INTO HEALTH_SCORE_HISTORY
    (SCAN_ID, SCAN_DATE, DATABASE_NAME, SCHEMA_NAME, TABLE_NAME,
     HEALTH_SCORE, COMPLETENESS_SCORE, UNIQUENESS_SCORE, VALIDITY_SCORE,
     CONSISTENCY_SCORE, INTEGRITY_SCORE, FRESHNESS_SCORE,
     TOTAL_ISSUES, CRITICAL_ISSUES, ROWS_AT_RISK)
VALUES
    -- Day 1: Poor quality (starting point)
    ('HIST_01', DATEADD(day, -5, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'CUSTOMERS', 58.50, 55.00, 60.00, 52.00, 65.00, 50.00, 85.00, 24, 5, 3200),
    ('HIST_01', DATEADD(day, -5, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'ORDERS',    62.00, 60.00, 65.00, 55.00, 68.00, 55.00, 80.00, 20, 4, 4500),
    ('HIST_01', DATEADD(day, -5, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'PRODUCTS',  72.00, 70.00, 75.00, 68.00, 74.00, 70.00, 88.00, 12, 2, 800),
    -- Day 2: Slight improvement
    ('HIST_02', DATEADD(day, -4, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'CUSTOMERS', 64.20, 62.00, 65.00, 58.00, 68.00, 58.00, 88.00, 19, 4, 2800),
    ('HIST_02', DATEADD(day, -4, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'ORDERS',    67.50, 65.00, 70.00, 60.00, 72.00, 62.00, 83.00, 16, 3, 3800),
    ('HIST_02', DATEADD(day, -4, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'PRODUCTS',  76.00, 74.00, 78.00, 72.00, 78.00, 74.00, 90.00,  9, 2, 600),
    -- Day 3: Improving
    ('HIST_03', DATEADD(day, -3, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'CUSTOMERS', 71.80, 70.00, 72.00, 65.00, 75.00, 68.00, 90.00, 14, 3, 2100),
    ('HIST_03', DATEADD(day, -3, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'ORDERS',    73.00, 72.00, 75.00, 68.00, 76.00, 70.00, 86.00, 12, 2, 2900),
    ('HIST_03', DATEADD(day, -3, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'PRODUCTS',  80.00, 78.00, 82.00, 76.00, 82.00, 78.00, 92.00,  7, 1, 450),
    -- Day 4: Good progress
    ('HIST_04', DATEADD(day, -2, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'CUSTOMERS', 78.50, 76.00, 80.00, 74.00, 82.00, 75.00, 92.00, 10, 2, 1500),
    ('HIST_04', DATEADD(day, -2, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'ORDERS',    79.00, 78.00, 80.00, 75.00, 80.00, 77.00, 90.00,  9, 2, 2100),
    ('HIST_04', DATEADD(day, -2, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'PRODUCTS',  84.00, 82.00, 86.00, 80.00, 85.00, 82.00, 93.00,  5, 1, 300),
    -- Day 5: Nearly there
    ('HIST_05', DATEADD(day, -1, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'CUSTOMERS', 83.20, 82.00, 85.00, 80.00, 85.00, 80.00, 94.00,  7, 1, 900),
    ('HIST_05', DATEADD(day, -1, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'ORDERS',    82.50, 81.00, 83.00, 80.00, 83.00, 82.00, 92.00,  7, 1, 1400),
    ('HIST_05', DATEADD(day, -1, CURRENT_DATE()), 'DATA_GUARDIAN_DB', 'DEMO_DATA', 'PRODUCTS',  87.00, 85.00, 88.00, 84.00, 88.00, 86.00, 95.00,  4, 0, 200),
    -- Day 6: Current state
    ('HIST_06', CURRENT_DATE(),                    'DATA_GUARDIAN_DB', 'DEMO_DATA', 'CUSTOMERS', 85.00, 84.00, 87.00, 82.00, 86.00, 82.00, 95.00,  6, 1, 750),
    ('HIST_06', CURRENT_DATE(),                    'DATA_GUARDIAN_DB', 'DEMO_DATA', 'ORDERS',    84.00, 83.00, 85.00, 82.00, 84.00, 83.00, 93.00,  6, 1, 1100),
    ('HIST_06', CURRENT_DATE(),                    'DATA_GUARDIAN_DB', 'DEMO_DATA', 'PRODUCTS',  88.50, 87.00, 89.00, 86.00, 89.00, 87.00, 95.00,  3, 0, 150);


-- ============================================================
-- 7. VERIFICATION
-- ============================================================

SELECT 'CUSTOMERS' AS tbl, COUNT(*) AS rows FROM DATA_GUARDIAN_DB.DEMO_DATA.CUSTOMERS
UNION ALL
SELECT 'PRODUCTS',         COUNT(*)         FROM DATA_GUARDIAN_DB.DEMO_DATA.PRODUCTS
UNION ALL
SELECT 'ORDERS',           COUNT(*)         FROM DATA_GUARDIAN_DB.DEMO_DATA.ORDERS
UNION ALL
SELECT 'QUALITY_RULES',    COUNT(*)         FROM DATA_GUARDIAN_DB.QUALITY_ENGINE.QUALITY_RULES
UNION ALL
SELECT 'SCORE_WEIGHTS',    COUNT(*)         FROM DATA_GUARDIAN_DB.QUALITY_ENGINE.SCORE_WEIGHTS
UNION ALL
SELECT 'HEALTH_HISTORY',   COUNT(*)         FROM DATA_GUARDIAN_DB.QUALITY_ENGINE.HEALTH_SCORE_HISTORY;

-- Expected output:
-- CUSTOMERS      ~5,025
-- PRODUCTS       ~510
-- ORDERS         ~20,022
-- QUALITY_RULES  16
-- SCORE_WEIGHTS  6
-- HEALTH_HISTORY 18

-- ============================================================
-- Setup complete! You can now deploy the Streamlit app.
-- ============================================================
