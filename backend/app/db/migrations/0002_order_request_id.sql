ALTER TABLE orders
    ADD COLUMN request_id UUID NOT NULL DEFAULT gen_random_uuid(),
    ADD CONSTRAINT orders_request_id_key UNIQUE (request_id);

ALTER TABLE orders ALTER COLUMN request_id DROP DEFAULT;
