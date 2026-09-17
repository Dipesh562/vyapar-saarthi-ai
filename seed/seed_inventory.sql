-- Vyapar Saarthi AI — Demo Inventory Seed Data (store_id = 1)
-- Idempotent loader script: deletes product_id 1..22 before re-inserting.

SET FOREIGN_KEY_CHECKS = 0;

-- 1. Ensure Pilot Store exists (store_id = 1)
INSERT INTO stores (store_id, name, address, language_pref)
VALUES (1, 'Karvenagar Kirana Store', 'Karvenagar, Pune', 'hi-en')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- 2. Clean existing seed rows for product_id 1..22 to maintain idempotency
DELETE FROM product_synonyms WHERE maps_to_product_id BETWEEN 1 AND 22;
DELETE FROM inventory WHERE product_id BETWEEN 1 AND 22;
DELETE FROM products WHERE product_id BETWEEN 1 AND 22;

-- 3. Insert Products (22 Products)
INSERT INTO products (product_id, store_id, name, normalized_name, unit, price, category, brand, is_active) VALUES
(1, 1, 'Madhur Sugar 1kg', 'madhur sugar 1kg', 'kg', 45.00, 'Staples', 'Madhur', 1),
(2, 1, 'Fortune Refined Sunflower Oil 1L', 'fortune refined sunflower oil 1l', 'packet', 145.00, 'Oil', 'Fortune', 1),
(3, 1, 'Saffola Gold Edible Oil 1L', 'saffola gold edible oil 1l', 'packet', 170.00, 'Oil', 'Saffola', 1),
(4, 1, 'Dhara Mustard Oil 1L', 'dhara mustard oil 1l', 'packet', 155.00, 'Oil', 'Dhara', 1),
(5, 1, 'Parle-G Biscuit 100g', 'parleg biscuit 100g', 'packet', 10.00, 'Snacks', 'Parle', 1),
(6, 1, 'Ashirvaad Whole Wheat Aata 5kg', 'ashirvaad whole wheat aata 5kg', 'packet', 260.00, 'Flour', 'Ashirvaad', 1),
(7, 1, 'Tata Salt 1kg', 'tata salt 1kg', 'packet', 28.00, 'Staples', 'Tata', 1),
(8, 1, 'Amul Butter 100g', 'amul butter 100g', 'packet', 58.00, 'Dairy', 'Amul', 1),
(9, 1, 'Amul Taaza Milk 500ml', 'amul taaza milk 500ml', 'packet', 27.00, 'Dairy', 'Amul', 1),
(10, 1, 'Toor Dal 1kg', 'toor dal 1kg', 'kg', 160.00, 'Pulses', 'Generic', 1),
(11, 1, 'Moong Dal 1kg', 'moong dal 1kg', 'kg', 135.00, 'Pulses', 'Generic', 1),
(12, 1, 'Basmati Rice 1kg', 'basmati rice 1kg', 'kg', 110.00, 'Rice', 'India Gate', 1),
(13, 1, 'Red Onion 1kg', 'red onion 1kg', 'kg', 35.00, 'Vegetables', 'Fresh', 1),
(14, 1, 'Potato 1kg', 'potato 1kg', 'kg', 30.00, 'Vegetables', 'Fresh', 1),
(15, 1, 'Tomato 1kg', 'tomato 1kg', 'kg', 40.00, 'Vegetables', 'Fresh', 1),
(16, 1, 'Maggie 2-Minute Noodles 70g', 'maggie 2minute noodles 70g', 'packet', 14.00, 'Snacks', 'Maggi', 1),
(17, 1, 'Brooke Bond Red Label Tea 250g', 'brooke bond red label tea 250g', 'packet', 140.00, 'Beverages', 'Red Label', 1),
(18, 1, 'Nescafé Classic Coffee 50g', 'nescafe classic coffee 50g', 'box', 185.00, 'Beverages', 'Nescafe', 1),
(19, 1, 'Surf Excel Quick Wash Detergent 1kg', 'surf excel quick wash detergent 1kg', 'packet', 150.00, 'Household', 'Surf Excel', 1),
(20, 1, 'Dettol Bathing Soap 75g', 'dettol bathing soap 75g', 'pc', 38.00, 'Personal Care', 'Dettol', 1),
(21, 1, 'Green Chilli 250g', 'green chilli 250g', 'packet', 20.00, 'Vegetables', 'Fresh', 1),
(22, 1, 'Garlic 250g', 'garlic 250g', 'packet', 45.00, 'Vegetables', 'Fresh', 1);

-- 4. Insert Inventory Levels (Product 21 Green Chilli is seeded LOW STOCK: 2.0 <= threshold 5.0)
INSERT INTO inventory (product_id, quantity_on_hand, low_stock_threshold) VALUES
(1, 50.000, 10.000),
(2, 25.000, 5.000),
(3, 20.000, 5.000),
(4, 15.000, 5.000),
(5, 100.000, 20.000),
(6, 30.000, 5.000),
(7, 40.000, 10.000),
(8, 15.000, 5.000),
(9, 30.000, 10.000),
(10, 25.000, 5.000),
(11, 20.000, 5.000),
(12, 35.000, 8.000),
(13, 40.000, 10.000),
(14, 50.000, 10.000),
(15, 30.000, 8.000),
(16, 80.000, 15.000),
(17, 20.000, 5.000),
(18, 12.000, 3.000),
(19, 18.000, 5.000),
(20, 45.000, 10.000),
(21, 2.000, 5.000), -- Deliberately seeded low stock!
(22, 10.000, 3.000);

-- 5. Insert Spoken Aliases / Synonyms (Multilingual & Regional registers: English, Hindi, Marathi, Hinglish)
INSERT INTO product_synonyms (store_id, term, maps_to_category, maps_to_product_id, language) VALUES
-- Product 1: Madhur Sugar 1kg
(1, 'sugar', 'Staples', 1, 'en'),
(1, 'sakhar', 'Staples', 1, 'mr'),
(1, 'cheeni', 'Staples', 1, 'hi'),
(1, 'madhur sugar', 'Staples', 1, 'hinglish'),

-- Product 2: Fortune Refined Sunflower Oil 1L
(1, 'fortune oil', 'Oil', 2, 'en'),
(1, 'fortune sunflower oil', 'Oil', 2, 'en'),
(1, 'tel', 'Oil', 2, 'hi'),
(1, 'fortune tel', 'Oil', 2, 'hinglish'),

-- Product 3: Saffola Gold Edible Oil 1L
(1, 'saffola oil', 'Oil', 3, 'en'),
(1, 'saffola gold', 'Oil', 3, 'en'),
(1, 'saffola tel', 'Oil', 3, 'hinglish'),

-- Product 4: Dhara Mustard Oil 1L
(1, 'dhara oil', 'Oil', 4, 'en'),
(1, 'dhara sarson tel', 'Oil', 4, 'hi'),
(1, 'sarson tel', 'Oil', 4, 'hi'),
(1, 'dhara tel', 'Oil', 4, 'hinglish'),

-- Product 5: Parle-G Biscuit 100g
(1, 'parle g', 'Snacks', 5, 'en'),
(1, 'parle-g', 'Snacks', 5, 'en'),
(1, 'parleg', 'Snacks', 5, 'en'),
(1, 'biscuit', 'Snacks', 5, 'en'),
(1, 'parle g biscuit', 'Snacks', 5, 'hinglish'),

-- Product 6: Ashirvaad Whole Wheat Aata 5kg
(1, 'aata', 'Flour', 6, 'hi'),
(1, 'ashirvaad aata', 'Flour', 6, 'hinglish'),
(1, 'gehun ka aata', 'Flour', 6, 'hi'),
(1, 'ashirvaad wheat flour', 'Flour', 6, 'en'),

-- Product 7: Tata Salt 1kg
(1, 'tata salt', 'Staples', 7, 'en'),
(1, 'namak', 'Staples', 7, 'hi'),
(1, 'tata namak', 'Staples', 7, 'hinglish'),
(1, 'salt', 'Staples', 7, 'en'),

-- Product 8: Amul Butter 100g
(1, 'amul butter', 'Dairy', 8, 'en'),
(1, 'makkhan', 'Dairy', 8, 'hi'),
(1, 'butter', 'Dairy', 8, 'en'),
(1, 'amul makkhan', 'Dairy', 8, 'hinglish'),

-- Product 9: Amul Taaza Milk 500ml
(1, 'doodh', 'Dairy', 9, 'hi'),
(1, 'milk', 'Dairy', 9, 'en'),
(1, 'amul milk', 'Dairy', 9, 'en'),
(1, 'amul doodh', 'Dairy', 9, 'hinglish'),

-- Product 10: Toor Dal 1kg
(1, 'toor dal', 'Pulses', 10, 'hi'),
(1, 'arhar dal', 'Pulses', 10, 'hi'),
(1, 'tuvar dal', 'Pulses', 10, 'mr'),
(1, 'varan dal', 'Pulses', 10, 'mr'),

-- Product 11: Moong Dal 1kg
(1, 'moong dal', 'Pulses', 11, 'hi'),
(1, 'mung dal', 'Pulses', 11, 'mr'),
(1, 'yellow dal', 'Pulses', 11, 'en'),

-- Product 12: Basmati Rice 1kg
(1, 'rice', 'Rice', 12, 'en'),
(1, 'chawal', 'Rice', 12, 'hi'),
(1, 'basmati rice', 'Rice', 12, 'en'),
(1, 'basmati chawal', 'Rice', 12, 'hinglish'),

-- Product 13: Red Onion 1kg
(1, 'kanda', 'Vegetables', 13, 'mr'),
(1, 'pyaz', 'Vegetables', 13, 'hi'),
(1, 'onion', 'Vegetables', 13, 'en'),
(1, 'red onion', 'Vegetables', 13, 'en'),

-- Product 14: Potato 1kg
(1, 'batata', 'Vegetables', 14, 'mr'),
(1, 'aalu', 'Vegetables', 14, 'hi'),
(1, 'potato', 'Vegetables', 14, 'en'),
(1, 'aloo', 'Vegetables', 14, 'hinglish'),

-- Product 15: Tomato 1kg
(1, 'tamatar', 'Vegetables', 15, 'hi'),
(1, 'tomato', 'Vegetables', 15, 'en'),
(1, 'tomatose', 'Vegetables', 15, 'en'),

-- Product 16: Maggie 2-Minute Noodles 70g
(1, 'maggi', 'Snacks', 16, 'en'),
(1, 'noodles', 'Snacks', 16, 'en'),
(1, 'maggie noodles', 'Snacks', 16, 'hinglish'),
(1, 'maggi packet', 'Snacks', 16, 'hinglish'),

-- Product 17: Brooke Bond Red Label Tea 250g
(1, 'chai', 'Beverages', 17, 'hi'),
(1, 'chai patti', 'Beverages', 17, 'hi'),
(1, 'red label tea', 'Beverages', 17, 'en'),
(1, 'tea', 'Beverages', 17, 'en'),

-- Product 18: Nescafé Classic Coffee 50g
(1, 'coffee', 'Beverages', 18, 'en'),
(1, 'nescafe', 'Beverages', 18, 'en'),
(1, 'nescafe coffee', 'Beverages', 18, 'en'),
(1, 'nescafe classic', 'Beverages', 18, 'en'),

-- Product 19: Surf Excel Quick Wash Detergent 1kg
(1, 'surf excel', 'Household', 19, 'en'),
(1, 'detergent', 'Household', 19, 'en'),
(1, 'nirma', 'Household', 19, 'hi'),
(1, 'kapde dhone ka powder', 'Household', 19, 'hi'),

-- Product 20: Dettol Bathing Soap 75g
(1, 'dettol', 'Personal Care', 20, 'en'),
(1, 'soap', 'Personal Care', 20, 'en'),
(1, 'sabun', 'Personal Care', 20, 'hi'),
(1, 'dettol sabun', 'Personal Care', 20, 'hinglish'),

-- Product 21: Green Chilli 250g
(1, 'hari mirchi', 'Vegetables', 21, 'hi'),
(1, 'green chilli', 'Vegetables', 21, 'en'),
(1, 'hirvi mirchi', 'Vegetables', 21, 'mr'),
(1, 'mirchi', 'Vegetables', 21, 'hi'),

-- Product 22: Garlic 250g
(1, 'lahsun', 'Vegetables', 22, 'hi'),
(1, 'lasun', 'Vegetables', 22, 'mr'),
(1, 'garlic', 'Vegetables', 22, 'en');

SET FOREIGN_KEY_CHECKS = 1;
