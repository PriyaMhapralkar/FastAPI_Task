-- Create a separate training schema
CREATE SCHEMA IF NOT EXISTS pms_agent_training;

SET search_path TO pms_agent_training;

-- 1. Tenant master
CREATE TABLE tenants (
    tenant_id VARCHAR(10) PRIMARY KEY,
    tenant_name VARCHAR(100) NOT NULL,
    business_type VARCHAR(60),
    contact_city VARCHAR(60),
    tenant_status VARCHAR(20) NOT NULL
);

INSERT INTO tenants VALUES
('T001', 'Mumbai Logistics Pvt Ltd', 'Logistics', 'Mumbai', 'ACTIVE'),
('T002', 'Coastal Warehousing Ltd', 'Warehousing', 'Mumbai', 'ACTIVE'),
('T003', 'Harbour Foods LLP', 'Food Processing', 'Navi Mumbai', 'ACTIVE'),
('T004', 'Oceanic Traders', 'Trading', 'Thane', 'INACTIVE'),
('T005', 'Western Shipping Services', 'Shipping', 'Mumbai', 'ACTIVE');

-- 2. Lease / property details
CREATE TABLE leases (
    lease_id VARCHAR(10) PRIMARY KEY,
    tenant_id VARCHAR(10) NOT NULL REFERENCES tenants(tenant_id),
    property_name VARCHAR(100) NOT NULL,
    property_type VARCHAR(50),
    monthly_rent NUMERIC(12,2) NOT NULL,
    lease_start DATE NOT NULL,
    lease_end DATE,
    lease_status VARCHAR(20) NOT NULL
);

INSERT INTO leases VALUES
('L001', 'T001', 'Warehouse A-101', 'WAREHOUSE', 50000, '2025-01-01', '2027-12-31', 'ACTIVE'),
('L002', 'T002', 'Plot B-202', 'PLOT', 75000, '2024-04-01', '2027-03-31', 'ACTIVE'),
('L003', 'T003', 'Unit C-303', 'INDUSTRIAL UNIT', 40000, '2025-07-01', '2028-06-30', 'ACTIVE'),
('L004', 'T004', 'Warehouse D-404', 'WAREHOUSE', 30000, '2023-01-01', '2025-12-31', 'EXPIRED'),
('L005', 'T005', 'Office E-505', 'OFFICE', 25000, '2025-04-01', '2027-03-31', 'ACTIVE'),
('L006', 'T001', 'Plot F-606', 'PLOT', 60000, '2025-10-01', '2028-09-30', 'ACTIVE');

-- 3. Rent bills
CREATE TABLE rent_bills (
    bill_id VARCHAR(10) PRIMARY KEY,
    lease_id VARCHAR(10) NOT NULL REFERENCES leases(lease_id),
    bill_date DATE NOT NULL,
    due_date DATE NOT NULL,
    bill_amount NUMERIC(12,2) NOT NULL CHECK (bill_amount >= 0)
);

INSERT INTO rent_bills VALUES
('B001', 'L001', '2026-07-01', '2026-07-15', 50000),
('B002', 'L001', '2026-08-01', '2026-08-15', 50000),
('B003', 'L002', '2026-08-01', '2026-08-15', 75000),
('B004', 'L002', '2026-09-01', '2026-09-15', 75000),
('B005', 'L003', '2026-09-01', '2026-09-15', 40000),
('B006', 'L005', '2026-09-01', '2026-09-15', 25000),
('B007', 'L006', '2026-09-01', '2026-09-15', 60000),
('B008', 'L001', '2026-09-01', '2026-09-15', 50000);

-- 4. Payments received against bills
CREATE TABLE payments (
    payment_id VARCHAR(10) PRIMARY KEY,
    bill_id VARCHAR(10) NOT NULL REFERENCES rent_bills(bill_id),
    payment_date DATE NOT NULL,
    amount_paid NUMERIC(12,2) NOT NULL CHECK (amount_paid > 0),
    payment_method VARCHAR(30),
    payment_status VARCHAR(20) NOT NULL
);

INSERT INTO payments VALUES
('P001', 'B001', '2026-07-10', 50000, 'ONLINE', 'SUCCESS'),
('P002', 'B002', '2026-08-10', 30000, 'ONLINE', 'SUCCESS'),
('P003', 'B003', '2026-08-12', 75000, 'BANK TRANSFER', 'SUCCESS'),
('P004', 'B004', '2026-09-10', 25000, 'ONLINE', 'SUCCESS'),
('P005', 'B005', '2026-09-12', 40000, 'ONLINE', 'SUCCESS'),
('P006', 'B006', '2026-09-14', 10000, 'BANK TRANSFER', 'SUCCESS'),
('P007', 'B007', '2026-09-14', 60000, 'ONLINE', 'SUCCESS'),
('P008', 'B008', '2026-09-16', 20000, 'ONLINE', 'SUCCESS');


