CREATE TABLE menus (
    menu_id TEXT PRIMARY KEY CHECK (btrim(menu_id) <> ''),
    name TEXT NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    price_krw INTEGER NOT NULL CHECK (price_krw >= 0),
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER NOT NULL CHECK (display_order > 0),
    is_featured BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE menu_categories (
    menu_id TEXT NOT NULL REFERENCES menus(menu_id) ON DELETE RESTRICT,
    category TEXT NOT NULL CHECK (
        category IN ('커피', '티', '에이드', '논커피라떼', '라떼')
    ),
    PRIMARY KEY (menu_id, category)
);

CREATE TABLE menu_variants (
    menu_id TEXT NOT NULL REFERENCES menus(menu_id) ON DELETE RESTRICT,
    temperature TEXT NOT NULL CHECK (temperature IN ('HOT', 'COLD')),
    image_url TEXT NOT NULL CHECK (image_url LIKE '/images/menus/%'),
    PRIMARY KEY (menu_id, temperature)
);

CREATE TABLE orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    menu_id TEXT NOT NULL REFERENCES menus(menu_id) ON DELETE RESTRICT,
    menu_name_snapshot TEXT NOT NULL CHECK (btrim(menu_name_snapshot) <> ''),
    unit_price_krw INTEGER NOT NULL CHECK (unit_price_krw >= 0),
    temperature TEXT NOT NULL CHECK (temperature IN ('HOT', 'COLD')),
    service_type TEXT NOT NULL CHECK (service_type IN ('DINE_IN', 'TAKEOUT')),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity = 1),
    total_price_krw INTEGER NOT NULL CHECK (
        total_price_krw >= 0 AND total_price_krw = unit_price_krw * quantity
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
