# stockflow-case-study-submission
My submission for the Backend Engineering Intern case study.



# Backend Engineering Intern Case Study Submission

This document contains the complete responses for the three parts of the StockFlow Inventory Management System case study.

---

## Part 1: Code Review & Debugging

[cite_start]This section addresses the issues found in the provided API endpoint for adding new products[cite: 9].

### 1. Identified Issues

* **Technical Issues:**
    * [cite_start]**Lack of Input Validation:** The code directly accesses `data['key']` without checking if the keys exist or if the values are valid[cite: 13].
    * **No Error Handling:** There is no `try...except` block to catch potential exceptions, which would cause the request to crash with a 500 Internal Server Error.
    * [cite_start]**Non-Atomic Transaction:** The `Product` and `Inventory` records are created in two separate database commits[cite: 22, 29], which can lead to data inconsistency if the second one fails.

* **Business Logic Issues:**
    * [cite_start]**SKU Uniqueness Violation:** The code does not check if a product with the given SKU already exists before attempting to create a new one, violating a core business requirement[cite: 36].
    * **Data Inconsistency:** If the product creation succeeds but the inventory creation fails, the system is left with an orphaned product that has no inventory record.

### 2. Explain Impact

* **Application Instability:** Malformed requests will cause the API to crash, leading to poor reliability and a bad user experience.
* **Data Corruption:** The non-atomic operations can lead to a state where a product exists in the `products` table but has no stock information, making the system's data untrustworthy.
* **Duplicate Records:** The failure to enforce SKU uniqueness would allow multiple products with the same SKU to be created, causing significant problems in warehouse management and order fulfillment.

### 3. Provide Fixes (Corrected Code)

```python
from flask import request, jsonify
from sqlalchemy.exc import IntegrityError

@app.route('/api/products', methods=['POST'])
def create_product():
    """
    Creates a new product and its initial inventory record in a single atomic transaction.
    """
    data = request.json

    # 1. Input Validation: Check for required fields and valid data types
    required_fields = ['name', 'sku', 'price', 'warehouse_id', 'initial_quantity']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # 2. Atomic Transaction and Error Handling
        # Check for existing SKU to enforce business rule
        if Product.query.filter_by(sku=data['sku']).first():
            return jsonify({"error": f"Product with SKU '{data['sku']}' already exists"}), 409

        # Create new product
        product = Product(
            name=data['name'],
            sku=data['sku'],
            price=float(data['price']),
            warehouse_id=data['warehouse_id']
        )
        db.session.add(product)
        db.session.flush() # Flush to get the product.id before commit

        # Create initial inventory count
        inventory = Inventory(
            product_id=product.id,
            warehouse_id=data['warehouse_id'],
            quantity=int(data['initial_quantity'])
        )
        db.session.add(inventory)

        # 3. Single commit for both operations
        db.session.commit()

        return jsonify({
            "message": "Product created successfully",
            "product_id": product.id
        }), 201

    except (ValueError, TypeError):
        db.session.rollback()
        return jsonify({"error": "Invalid data type for price or initial_quantity"}), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Database integrity error. SKU might already exist."}), 409
    except Exception as e:
        db.session.rollback()
        # In a real app, log the error 'e'
        return jsonify({"error": "An unexpected error occurred."}), 500

```

### Reasoning for Decisions (Part 1)

* **Data Integrity:** The primary decision was to wrap the database operations in a single `try...except` block and use a single `db.session.commit()`. This makes the creation of a product and its inventory an **atomic transaction**. If any step fails, `db.session.rollback()` is called, ensuring the database remains in a consistent state.
* **Proactive Business Rule Enforcement:** A query was added to check for an existing SKU *before* attempting to insert a new one. This provides a clearer error message (`409 Conflict`) to the user and prevents the database from throwing a generic error.
* **Robustness:** Input validation was added to catch missing fields and invalid data types early, returning a helpful `400 Bad Request` error. This prevents the application from crashing on bad data and immediately informs the client of the issue.

---

## Part 2: Database Design

### 1. Design Schema (SQL DDL)

```sql
-- Companies that use the StockFlow platform
CREATE TABLE companies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Warehouses owned by companies
CREATE TABLE warehouses (
    id INT PRIMARY KEY AUTO_INCREMENT,
    company_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
);

-- Suppliers who provide products
CREATE TABLE suppliers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product categories to manage different types of products and rules like stock thresholds
CREATE TABLE product_types (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    low_stock_threshold INT NOT NULL DEFAULT 20
);

-- Core product information
CREATE TABLE products (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sku VARCHAR(100) NOT NULL UNIQUE, -- SKU must be unique across the platform
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL, -- Price can be decimal values
    product_type_id INT,
    supplier_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_type_id) REFERENCES product_types(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
);

-- Junction table for inventory, tracking product quantity in each warehouse
CREATE TABLE inventory (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    warehouse_id INT NOT NULL,
    quantity INT NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE (product_id, warehouse_id), -- A product can only have one entry per warehouse
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE
);

-- Tracks changes to inventory levels for auditing and analysis
CREATE TABLE inventory_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    inventory_id INT NOT NULL,
    change_amount INT NOT NULL, -- e.g., -5 for a sale, +50 for restocking
    new_quantity INT NOT NULL,
    reason VARCHAR(255), -- e.g., 'sale', 'restock', 'correction'
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (inventory_id) REFERENCES inventory(id)
);

-- Junction table to handle product bundles
CREATE TABLE product_bundles (
    bundle_product_id INT NOT NULL, -- The ID of the product that is a bundle
    component_product_id INT NOT NULL, -- The ID of a product contained within the bundle
    quantity_in_bundle INT NOT NULL,
    PRIMARY KEY (bundle_product_id, component_product_id),
    FOREIGN KEY (bundle_product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (component_product_id) REFERENCES products(id) ON DELETE CASCADE
);
```

### 2. Identify Gaps (Questions for Product Team)

1.  **Product Bundles:** How should the inventory of a "bundle" product be managed? Is it a virtual count based on the stock of its components, or are bundles pre-assembled with their own physical stock count?
2.  **Inventory Change Tracking:** What specific events should trigger an `inventory_logs` entry (e.g., sales, returns, new stock arrivals) to satisfy the requirement to "Track when inventory levels change"?
3.  **"Recent Sales Activity":** What is the exact definition of "recent" for low-stock alerts? Is it the last 7 days, 30 days, or a configurable period?
4.  **Suppliers:** Can a single product be supplied by multiple suppliers ? If so, the schema would need a many-to-many relationship table.
5.  **User Roles:** What are the different user roles (e.g., admin, warehouse manager), and what are their permissions for modifying inventory?

### 3. Explain Decisions (Design Justification)

* **Normalization:** The schema is normalized to reduce data redundancy.
* For example, `inventory` is a junction table that correctly models the many-to-many relationship where a product can be in multiple warehouses and a warehouse can hold multiple products.
* **Data Integrity and Constraints:**
    * The `UNIQUE` constraint on `products.sku` programmatically enforces the business rule that SKUs must be unique.
    * The composite `UNIQUE` key `(product_id, warehouse_id)` in the `inventory` table ensures that a product cannot have duplicate stock entries for the same warehouse.
    * Foreign keys with `ON DELETE CASCADE` maintain referential integrity. For instance, if a company is deleted, all of its associated warehouses are automatically removed.
**Auditability:** The `inventory_logs` table was created to explicitly satisfy the requirement to track inventory changes, providing a crucial audit trail for debugging and business analysis.
**Flexibility:** The `product_types` table allows business rules, like the low-stock threshold, to be easily configured per product type instead of being hardcoded.

---

## Part 3: API Implementation

### 1. Implementation (Python/Flask)

//This implementation provides the endpoint to return low-stock alerts for a company.

```python
from flask import jsonify
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta

# Assumptions:
# - Models (Product, Warehouse, Inventory, Supplier, etc.) are defined based on Part 2.
# - "Recent sales" means sales within the last 30 days.
# - `days_until_stockout` is based on average daily sales over that period.

@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def get_low_stock_alerts(company_id):
    """
    Returns low-stock alerts for a given company.
    """
    # 1. Define Business Logic Variables
    recent_period_days = 30
    activity_since_date = datetime.utcnow() - timedelta(days=recent_period_days)

    # 2. Query to Fetch Low-Stock Items with Recent Sales
    # This single query joins all necessary tables and filters based on the business rules.
    # Note: A subquery could be used for optimization on very large datasets.
    low_stock_query = db.session.query(
        Inventory, Product, Warehouse, ProductType, Supplier,
        # Calculate total recent sales for this item
        db.func.sum(SalesActivity.quantity_sold).label('total_sold')
    ).join(Product, Inventory.product_id == Product.id)\
     .join(Warehouse, Inventory.warehouse_id == Warehouse.id)\
     .join(ProductType, Product.product_type_id == ProductType.id)\
     .outerjoin(Supplier, Product.supplier_id == Supplier.id)\
     .join(SalesActivity, db.and_(
            SalesActivity.product_id == Inventory.product_id,
            SalesActivity.warehouse_id == Inventory.warehouse_id
     ))\
     .filter(Warehouse.company_id == company_id)\
     .filter(SalesActivity.sale_date >= activity_since_date)\
     .filter(Inventory.quantity <= ProductType.low_stock_threshold)\
     .group_by(Inventory.id, Product.id, Warehouse.id, ProductType.id, Supplier.id)

    alerts_data = low_stock_query.all()

    # 3. Format the Response
    alerts = []
    for inventory, product, warehouse, product_type, supplier, total_sold in alerts_data:
        days_until_stockout = None
        if total_sold and total_sold > 0:
            avg_daily_sales = total_sold / recent_period_days
            if avg_daily_sales > 0:
                days_until_stockout = int(inventory.quantity / avg_daily_sales)

        alerts.append({
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "current_stock": inventory.quantity,
            "threshold": product_type.low_stock_threshold,
            "days_until_stockout": days_until_stockout,
            "supplier": {
                "id": supplier.id if supplier else None,
                "name": supplier.name if supplier else None,
                "contact_email": supplier.contact_email if supplier else None
            }
        })

    return jsonify({"alerts": alerts, "total_alerts": len(alerts)})
```

### 2. Handle Edge Cases

* **Company Not Found:** The query for a non-existent `company_id` will correctly return an empty list of alerts. A more robust solution would add an initial check for the company's existence and return a 404 error.
* **No Recent Sales:** If a product is low on stock but has not been sold in the last 30 days, it is correctly excluded from the alerts by the `filter(SalesActivity.sale_date >= ...)` condition.
* **Product without a Supplier:** The use of `outerjoin(Supplier, ...)` ensures that alerts are still generated for products that do not have an assigned supplier.The supplier object in the response will correctly contain `null` values.
* **Division by Zero:** The `days_until_stockout` calculation is protected by checking if `avg_daily_sales` is greater than zero, preventing a runtime error.

### 3. Explain Approach

 **Single Comprehensive Query:** The approach uses a single, powerful SQLAlchemy query to join all necessary tables (`Inventory`, `Product`, `Warehouse`, `Supplier`, etc.). This is efficient as it gathers all required data in one database roundtrip.
 **Direct Filtering:** The business rules are translated directly into `filter()` conditions in the query.
 This includes filtering by company, checking for recent sales activity, and comparing the current stock against the product type's threshold.
 **Data Transformation:** After fetching the data, the code iterates through the results and transforms them into the required JSON format. This layer is also responsible for post-query calculations, like `days_until_stockout`.

---

## Assumptions Made

Due to incomplete requirements, the following assumptions were made to complete the tasks:

1.  **Framework and ORM:** The code solutions assume a Python/Flask stack with the SQLAlchemy ORM, as suggested by the syntax in Part 1.
2.  **Definition of "Recent Sales Activity":** I assumed "recent" means a fixed period of the last 30 days to fulfill the requirement that alerts are only for products with recent sales activity  .
3.  **Stockout Calculation:** The `days_until_stockout` value is assumed to be a simple linear projection based on average daily sales over the "recent" period.
4.  **Database Schema for API:** The API implementation in Part 3 assumes the database schema designed in Part 2 is in place.
5.  **Authentication and Authorization:** The API implementation omits any checks to verify that the requesting user has permission to view data for the given `{company_id}`. This would be a critical requirement in a production system.
