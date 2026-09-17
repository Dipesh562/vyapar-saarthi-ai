import csv
import io
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from decimal import Decimal
from app.extensions import db
from app.models import Product, Inventory, InventoryMovement
from app.utils.decorators import require_role

inventory_csv_bp = Blueprint('inventory_csv', __name__, url_prefix='/api/v1/products/import')

@inventory_csv_bp.route('/preview', methods=['POST'])
@require_role('owner')
def preview_csv_import():
    """
    POST /api/v1/products/import/preview
    Parses a CSV file, validates rows, and returns a preview of valid/invalid records.
    """
    if 'file' not in request.files:
        return jsonify({
            "error": {
                "code": "MISSING_FILE",
                "message": "No file part in the request."
            }
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            "error": {
                "code": "NO_FILE_SELECTED",
                "message": "No selected file."
            }
        }), 400

    if not file.filename.endswith('.csv'):
        return jsonify({
            "error": {
                "code": "INVALID_FILE_TYPE",
                "message": "Only CSV files are allowed."
            }
        }), 400

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        # Normalize headers to lowercase and strip spaces
        headers = [h.strip().lower() for h in csv_input.fieldnames]
        
        # We need a mapping from possible header names to our expected keys
        header_mapping = {}
        for h in headers:
            if 'name' in h and 'product' in h: header_mapping[h] = 'name'
            elif h == 'name': header_mapping[h] = 'name'
            elif 'brand' in h: header_mapping[h] = 'brand'
            elif 'category' in h: header_mapping[h] = 'category'
            elif 'selling' in h or 'price' in h and 'cost' not in h: header_mapping[h] = 'price'
            elif 'cost' in h: header_mapping[h] = 'cost_price'
            elif 'unit' in h: header_mapping[h] = 'unit'
            elif 'stock' in h and 'low' not in h: header_mapping[h] = 'stock'
            elif 'low' in h and 'threshold' in h: header_mapping[h] = 'threshold'
            elif 'sku' in h: header_mapping[h] = 'sku'
            elif 'barcode' in h: header_mapping[h] = 'barcode'
            else: header_mapping[h] = h # Keep as is if unmapped
            
        valid_rows = []
        invalid_rows = []
        
        for row_index, row in enumerate(csv_input, start=1):
            # Map the row data
            mapped_row = {header_mapping.get(k.strip().lower(), k.strip().lower()): v.strip() for k, v in row.items() if k and v}
            
            # Validation
            errors = []
            
            name = mapped_row.get('name')
            if not name:
                errors.append("Product name is required")
                
            unit = mapped_row.get('unit', 'piece')
            if not unit:
                unit = 'piece' # Default
                
            try:
                price_str = mapped_row.get('price')
                price = float(price_str) if price_str else None
                if price is None:
                    errors.append("Selling price is required")
            except ValueError:
                errors.append(f"Invalid selling price: {mapped_row.get('price')}")
                
            try:
                cost_str = mapped_row.get('cost_price')
                cost_price = float(cost_str) if cost_str else None
            except ValueError:
                errors.append(f"Invalid cost price: {mapped_row.get('cost_price')}")
                
            try:
                stock_str = mapped_row.get('stock', '0')
                stock = float(stock_str)
            except ValueError:
                errors.append(f"Invalid stock value: {mapped_row.get('stock')}")
                
            try:
                thresh_str = mapped_row.get('threshold', '0')
                threshold = float(thresh_str)
            except ValueError:
                errors.append(f"Invalid threshold value: {mapped_row.get('threshold')}")
                
            row_data = {
                "row_index": row_index,
                "name": name,
                "brand": mapped_row.get('brand'),
                "category": mapped_row.get('category'),
                "price": price if not errors else mapped_row.get('price'),
                "cost_price": cost_price if not errors and cost_price is not None else None,
                "unit": unit,
                "stock": stock if not errors else mapped_row.get('stock'),
                "threshold": threshold if not errors else mapped_row.get('threshold'),
                "sku": mapped_row.get('sku'),
                "barcode": mapped_row.get('barcode'),
            }
            
            if errors:
                row_data["errors"] = errors
                invalid_rows.append(row_data)
            else:
                valid_rows.append(row_data)
                
        return jsonify({
            "total_rows": len(valid_rows) + len(invalid_rows),
            "valid_count": len(valid_rows),
            "invalid_count": len(invalid_rows),
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows
        }), 200

    except Exception as e:
        return jsonify({
            "error": {
                "code": "CSV_PARSE_ERROR",
                "message": f"Error parsing CSV file: {str(e)}"
            }
        }), 500

@inventory_csv_bp.route('/confirm', methods=['POST'])
@require_role('owner')
def confirm_csv_import():
    """
    POST /api/v1/products/import/confirm
    Takes a JSON list of validated rows and inserts them into the database.
    """
    data = request.get_json() or {}
    rows = data.get('rows', [])
    
    if not rows or not isinstance(rows, list):
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Valid rows array is required."
            }
        }), 400
        
    store_id = current_user.store_id
    success_count = 0
    errors = []
    
    try:
        for index, row in enumerate(rows):
            name = row.get('name')
            price = row.get('price')
            unit = row.get('unit', 'piece')
            
            if not name or price is None:
                errors.append(f"Row {index}: Name and price required.")
                continue
                
            normalized_name = Product.normalize_product_name(name)
            
            # Check if product with same normalized name exists
            existing_product = Product.query.filter_by(
                store_id=store_id, 
                normalized_name=normalized_name,
                is_active=True
            ).first()
            
            if existing_product:
                errors.append(f"Row {index}: Product '{name}' already exists.")
                continue
                
            # Create product
            product = Product(
                store_id=store_id,
                name=name,
                normalized_name=normalized_name,
                unit=unit,
                price=price,
                category=row.get('category'),
                brand=row.get('brand'),
                cost_price=row.get('cost_price'),
                sku=row.get('sku'),
                barcode=row.get('barcode')
            )
            db.session.add(product)
            db.session.flush() # To get product_id
            
            # Create inventory
            initial_stock = row.get('stock', 0)
            threshold = row.get('threshold', 0)
            
            inventory = Inventory(
                product_id=product.product_id,
                quantity_on_hand=initial_stock,
                low_stock_threshold=threshold
            )
            db.session.add(inventory)
            
            # If stock > 0, create movement
            if initial_stock > 0:
                movement = InventoryMovement(
                    store_id=store_id,
                    product_id=product.product_id,
                    movement_type='STOCK_IN',
                    quantity=initial_stock,
                    previous_stock=0,
                    new_stock=initial_stock,
                    reason="CSV Import"
                )
                db.session.add(movement)
                
            success_count += 1
            
        db.session.commit()
        
        return jsonify({
            "message": f"Successfully imported {success_count} products.",
            "imported_count": success_count,
            "errors": errors
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "error": {
                "code": "IMPORT_FAILED",
                "message": str(e)
            }
        }), 500
