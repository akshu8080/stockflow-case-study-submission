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
