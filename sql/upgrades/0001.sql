CREATE TABLE IF NOT EXISTS contact_message (
    id serial NOT NULL PRIMARY KEY,
    cig_id integer NOT NULL REFERENCES contact_in_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    send_date timestamp without time zone NOT NULL,
    read_date timestamp without time zone,
    is_answer boolean DEFAULT false NOT NULL,
    text text,
    sync_info text
);
ALTER TABLE contact_group DROP COLUMN IF EXISTS has_news;
SET TIMEZONE TO UTC;
ALTER TABLE contact_group_news ALTER COLUMN "date" TYPE timestamp with time zone;
ALTER TABLE contact_message ALTER COLUMN send_date TYPE timestamp with time zone;
ALTER TABLE contact_message ALTER COLUMN read_date TYPE timestamp with time zone;
ALTER TABLE contact_group ALTER COLUMN "date" TYPE timestamp with time zone;
DROP SEQUENCE IF EXISTS contact_field_value_contact_id_seq CASCADE;

UPDATE contact_in_group SET flags = flags|32768|65536 WHERE (flags & 8) <> 0;
UPDATE contact_in_group SET flags = flags|32768 WHERE (flags & 16) <> 0;
UPDATE group_manage_group SET flags = flags|32768|65536 WHERE (flags & 8) <> 0;
UPDATE group_manage_group SET flags = flags|32768 WHERE (flags & 16) <> 0;

SET TIMEZONE TO UTC;
ALTER TABLE contact_group ALTER COLUMN "date" TYPE date;
ALTER TABLE log  ALTER COLUMN "dt" TYPE timestamp with time zone;
