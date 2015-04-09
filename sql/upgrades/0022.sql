-- Remove oids, replace by a 'django_id' primary key
ALTER TABLE choice DROP CONSTRAINT choice_pkey;
CREATE UNIQUE INDEX choice_choice_group_id_key_key ON choice (choice_group_id, key);
ALTER TABLE choice ADD COLUMN django_id serial NOT NULL PRIMARY KEY;
ALTER TABLE choice SET WITHOUT OIDS;

ALTER TABLE contact_field_value DROP CONSTRAINT contact_field_value_pkey;
CREATE UNIQUE INDEX contact_field_value_contact_id_contact_field_id_key ON contact_field_value (contact_id, contact_field_id);
ALTER TABLE contact_field_value ADD COLUMN django_id serial NOT NULL PRIMARY KEY;
ALTER TABLE contact_field_value SET WITHOUT OIDS;

ALTER TABLE group_in_group DROP CONSTRAINT group_in_group_pkey;
CREATE UNIQUE INDEX group_in_group_father_id_subgroup_id_key ON group_in_group (father_id, subgroup_id);
ALTER TABLE group_in_group ADD COLUMN django_id serial NOT NULL PRIMARY KEY;
ALTER TABLE group_in_group SET WITHOUT OIDS;

ALTER TABLE group_manage_group DROP CONSTRAINT group_manage_group_pkey;
CREATE UNIQUE INDEX group_manage_group_father_id_subgroup_id_key ON group_manage_group (father_id, subgroup_id);
ALTER TABLE group_manage_group ADD COLUMN django_id serial NOT NULL PRIMARY KEY;
ALTER TABLE group_manage_group SET WITHOUT OIDS;
