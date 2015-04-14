ALTER TABLE contact_group ALTER COLUMN field_group DROP DEFAULT;
ALTER TABLE contact_group ALTER COLUMN budget_code DROP DEFAULT;
ALTER TABLE contact_group ALTER COLUMN system DROP DEFAULT;
ALTER TABLE contact_group ALTER COLUMN sticky DROP DEFAULT;

ALTER TABLE choice_group ALTER COLUMN sort_by_key DROP DEFAULT;

ALTER TABLE choice ALTER COLUMN key DROP DEFAULT;
ALTER TABLE choice ALTER COLUMN value DROP DEFAULT;

ALTER TABLE contact_field ALTER COLUMN "type" DROP DEFAULT;
ALTER TABLE contact_field ALTER COLUMN "system" DROP DEFAULT;

ALTER TABLE contact_message ALTER COLUMN is_answer DROP DEFAULT;
ALTER TABLE contact_message ALTER COLUMN subject DROP DEFAULT;
