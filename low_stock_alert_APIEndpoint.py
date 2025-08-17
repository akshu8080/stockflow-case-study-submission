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
