UPDATE config SET "text"='' WHERE "text" IS NULL;
ALTER TABLE config ALTER COLUMN "text" SET NOT NULL;
CREATE INDEX config_id_like ON config USING btree (id varchar_pattern_ops);

CREATE INDEX contact_name_like ON contact USING btree (name varchar_pattern_ops);

UPDATE contact_group SET description='' WHERE description IS NULL;
ALTER TABLE contact_group ALTER COLUMN description SET NOT NULL;
UPDATE contact_group SET mailman_address='' WHERE mailman_address IS NULL;
ALTER TABLE contact_group ALTER COLUMN mailman_address SET NOT NULL;

DROP INDEX IF EXISTS choice_choice_group_id_index;
CREATE INDEX choice_choice_group_id ON choice USING btree (choice_group_id);

UPDATE contact_field SET hint='' WHERE hint IS NULL;
ALTER TABLE contact_field ALTER COLUMN hint SET NOT NULL;
UPDATE contact_field SET "default"='' WHERE "default" IS NULL;
ALTER TABLE contact_field ALTER COLUMN "default" SET NOT NULL;
CREATE INDEX contact_field_choice_group2_id ON contact_field USING btree (choice_group2_id);
CREATE INDEX contact_field_choice_group_id ON contact_field USING btree (choice_group_id);
CREATE INDEX contact_field_contact_group_id ON contact_field USING btree (contact_group_id);

UPDATE contact_field_value SET value='' WHERE value IS NULL;
ALTER TABLE contact_field_value ALTER COLUMN value SET NOT NULL;
DROP INDEX IF EXISTS contact_field_value_contact_id_index;
DROP INDEX IF EXISTS contact_field_value_contact_field_id_index;
CREATE INDEX contact_field_value_contact_field_id ON contact_field_value USING btree (contact_field_id);
CREATE INDEX contact_field_value_contact_id ON contact_field_value USING btree (contact_id);

UPDATE contact_in_group SET note='' WHERE note IS NULL;
ALTER TABLE contact_in_group ALTER COLUMN note SET NOT NULL;

DROP INDEX IF EXISTS contact_in_group_contact_id_index;
DROP INDEX IF EXISTS contact_in_group_group_id_index;
CREATE INDEX contact_in_group_contact_id ON contact_in_group USING btree (contact_id);
CREATE INDEX contact_in_group_group_id ON contact_in_group USING btree (group_id);

CREATE INDEX contact_group_news_author_id ON contact_group_news USING btree (author_id);
CREATE INDEX contact_group_news_contact_group_id ON contact_group_news USING btree (contact_group_id);

DROP INDEX IF EXISTS group_in_group_contact_id_index;
DROP INDEX IF EXISTS group_in_group_group_id_index;
CREATE INDEX group_in_group_father_id ON group_in_group USING btree (father_id);
CREATE INDEX group_in_group_subgroup_id ON group_in_group USING btree (subgroup_id);

DROP INDEX IF EXISTS group_manage_group_contact_id_index;
DROP INDEX IF EXISTS group_manage_group_group_id_index;
CREATE INDEX group_manage_group_father_id ON group_manage_group USING btree (father_id);
CREATE INDEX group_manage_group_subgroup_id ON group_manage_group USING btree (subgroup_id);

CREATE INDEX log_contact_id ON log USING btree (contact_id);

UPDATE contact_message SET "text"='' WHERE "text" IS NULL;
ALTER TABLE contact_message ALTER COLUMN "text" SET NOT NULL;
UPDATE contact_message SET sync_info='' WHERE sync_info IS NULL;
ALTER TABLE contact_message ALTER COLUMN "sync_info" SET NOT NULL;
CREATE INDEX contact_message_contact_id ON contact_message USING btree (contact_id);
CREATE INDEX contact_message_group_id ON contact_message USING btree (group_id);
CREATE INDEX contact_message_read_by_id ON contact_message USING btree (read_by_id);
