ALTER TABLE menu_categories DROP CONSTRAINT menu_categories_category_check;
ALTER TABLE menu_categories ADD CONSTRAINT menu_categories_category_check CHECK (
    category IN ('커피', '디카페인', '음료', '에스프레소', '라떼', '콜드브루',
                 '에이드', '프라페', '스무디/주스', '논커피라떼', '티')
);

ALTER TABLE menu_variants ADD COLUMN option_groups JSONB NOT NULL DEFAULT '[]'
    CHECK (jsonb_typeof(option_groups) = 'array');
ALTER TABLE orders ADD COLUMN selected_options JSONB NOT NULL DEFAULT '[]'
    CHECK (jsonb_typeof(selected_options) = 'array');
