from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Product, Inventory
from app.utils.decorators import require_role

products_bp = Blueprint('products', __name__, url_prefix='/api/v1/products')

@products_bp.route('', methods=['GET'])
@login_required
def list_products():
    """
    GET /api/v1/products
    List all active products for the authenticated user's store.
    """
    products = Product.query.filter_by(store_id=current_user.store_id, is_active=True).all()
    result = []
    for p in products:
        result.append({
            "product_id": p.product_id,
            "name": p.name,
            "normalized_name": p.normalized_name,
            "unit": p.unit,
            "price": float(p.price),
            "category": p.category,
            "brand": p.brand,
            "cost_price": float(p.cost_price) if p.cost_price is not None else None,
            "sku": p.sku,
            "barcode": p.barcode,
            "image_url": p.image_url,
            "quantity_on_hand": float(p.inventory.quantity_on_hand) if p.inventory else 0.0,
            "low_stock_threshold": float(p.inventory.low_stock_threshold) if p.inventory else 0.0,
            "is_low_stock": p.inventory.is_low_stock if p.inventory else False,
            "stock_status": p.inventory.stock_status if p.inventory else "out_of_stock"
        })
    return jsonify(result), 200

@products_bp.route('', methods=['POST'])
@require_role('owner')
def create_product():
    """
    POST /api/v1/products
    Create a new product (Owner only). Computes normalized_name and creates inventory record.
    """
    data = request.get_json() or {}
    name = data.get('name')
    unit = data.get('unit')
    price = data.get('price')

    if not all([name, unit, price is not None]):
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "name, unit, and price are required."
            }
        }), 400

    normalized_name = Product.normalize_product_name(name)
    initial_stock = data.get('quantity_on_hand', 0)
    low_stock_threshold = data.get('low_stock_threshold', 0)

    try:
        product = Product(
            store_id=current_user.store_id,
            name=name,
            normalized_name=normalized_name,
            unit=unit,
            price=price,
            category=data.get('category'),
            brand=data.get('brand'),
            cost_price=data.get('cost_price'),
            sku=data.get('sku'),
            barcode=data.get('barcode'),
            image_url=data.get('image_url')
        )
        db.session.add(product)
        db.session.flush()

        inventory = Inventory(
            product_id=product.product_id,
            quantity_on_hand=initial_stock,
            low_stock_threshold=low_stock_threshold
        )
        db.session.add(inventory)
        db.session.commit()

        return jsonify({
            "message": "Product created successfully.",
            "product": {
                "product_id": product.product_id,
                "name": product.name,
                "normalized_name": product.normalized_name,
                "unit": product.unit,
                "price": float(product.price),
                "category": product.category,
                "brand": product.brand,
                "cost_price": float(product.cost_price) if product.cost_price is not None else None,
                "sku": product.sku,
                "barcode": product.barcode,
                "image_url": product.image_url,
                "quantity_on_hand": float(inventory.quantity_on_hand),
                "low_stock_threshold": float(inventory.low_stock_threshold),
                "stock_status": inventory.stock_status
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": {
                "code": "CREATE_PRODUCT_FAILED",
                "message": str(e)
            }
        }), 500

@products_bp.route('/<int:product_id>', methods=['PATCH'])
@require_role('owner')
def update_product(product_id):
    """
    PATCH /api/v1/products/{id}
    Update product details (Owner only). Price edits are strictly owner-only.
    """
    product = Product.query.filter_by(product_id=product_id, store_id=current_user.store_id, is_active=True).first()
    if not product:
        return jsonify({
            "error": {
                "code": "PRODUCT_NOT_FOUND",
                "message": f"Product with ID {product_id} not found."
            }
        }), 404

    data = request.get_json() or {}
    if 'name' in data:
        product.name = data['name']
        product.normalized_name = Product.normalize_product_name(data['name'])
    if 'unit' in data:
        product.unit = data['unit']
    if 'price' in data:
        product.price = data['price']
    if 'category' in data:
        product.category = data['category']
    if 'brand' in data:
        product.brand = data['brand']
    if 'cost_price' in data:
        product.cost_price = data['cost_price']
    if 'sku' in data:
        product.sku = data['sku']
    if 'barcode' in data:
        product.barcode = data['barcode']
    if 'image_url' in data:
        product.image_url = data['image_url']
    if 'low_stock_threshold' in data and product.inventory:
        product.inventory.low_stock_threshold = data['low_stock_threshold']

    db.session.commit()

    return jsonify({
        "message": "Product updated successfully.",
        "product": {
            "product_id": product.product_id,
            "name": product.name,
            "normalized_name": product.normalized_name,
            "unit": product.unit,
            "price": float(product.price),
            "category": product.category,
            "brand": product.brand,
            "cost_price": float(product.cost_price) if product.cost_price is not None else None,
            "sku": product.sku,
            "barcode": product.barcode,
            "image_url": product.image_url,
            "low_stock_threshold": float(product.inventory.low_stock_threshold) if product.inventory else 0.0
        }
    }), 200
@products_bp.route('/<int:product_id>', methods=['DELETE'])
@require_role('owner')
def delete_product(product_id):
    """
    DELETE /api/v1/products/{id}
    Soft delete a product (Owner only).
    """
    product = Product.query.filter_by(product_id=product_id, store_id=current_user.store_id, is_active=True).first()
    if not product:
        return jsonify({
            "error": {
                "code": "PRODUCT_NOT_FOUND",
                "message": f"Product with ID {product_id} not found."
            }
        }), 404

    product.is_active = False
    db.session.commit()

    return jsonify({"message": "Product deleted successfully."}), 200

@products_bp.route('/stats', methods=['GET'])
@login_required
def get_inventory_stats():
    """
    GET /api/v1/products/stats
    Returns inventory dashboard stats.
    """
    products = Product.query.filter_by(store_id=current_user.store_id, is_active=True).all()
    
    total_products = len(products)
    in_stock = 0
    low_stock = 0
    out_of_stock = 0
    
    for p in products:
        if p.inventory:
            status = p.inventory.stock_status
            if status == "in_stock":
                in_stock += 1
            elif status == "low_stock":
                low_stock += 1
            elif status == "out_of_stock":
                out_of_stock += 1
        else:
            out_of_stock += 1
            
    return jsonify({
        "total_products": total_products,
        "in_stock": in_stock,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock
    }), 200

@products_bp.route('/search', methods=['GET'])
@login_required
def search_products():
    """
    GET /api/v1/products/search
    Search and filter products.
    Query params: q (search term), filter (all, in_stock, low_stock, out_of_stock, category_name)
    """
    query_term = request.args.get('q', '').lower()
    filter_type = request.args.get('filter', 'all')
    
    products_query = Product.query.filter_by(store_id=current_user.store_id, is_active=True)
    products = products_query.all()
    
    result = []
    for p in products:
        # Filtering
        if filter_type != 'all':
            if filter_type in ['in_stock', 'low_stock', 'out_of_stock']:
                status = p.inventory.stock_status if p.inventory else 'out_of_stock'
                if status != filter_type:
                    continue
            else: # Assume it's a category filter
                if not p.category or p.category.lower() != filter_type.lower():
                    continue
                    
        # Searching
        if query_term:
            match_found = False
            if query_term in p.name.lower():
                match_found = True
            elif p.brand and query_term in p.brand.lower():
                match_found = True
            elif p.sku and query_term in p.sku.lower():
                match_found = True
            elif p.barcode and query_term in p.barcode.lower():
                match_found = True
                
            if not match_found:
                continue
                
        result.append({
            "product_id": p.product_id,
            "name": p.name,
            "unit": p.unit,
            "price": float(p.price),
            "category": p.category,
            "brand": p.brand,
            "cost_price": float(p.cost_price) if p.cost_price is not None else None,
            "sku": p.sku,
            "barcode": p.barcode,
            "image_url": p.image_url,
            "quantity_on_hand": float(p.inventory.quantity_on_hand) if p.inventory else 0.0,
            "low_stock_threshold": float(p.inventory.low_stock_threshold) if p.inventory else 0.0,
            "stock_status": p.inventory.stock_status if p.inventory else "out_of_stock"
        })
        
    return jsonify(result), 200
