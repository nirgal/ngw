ALTER TABLE contact_field ADD COLUMN choice_group2_id INTEGER REFERENCES choice_group(id) MATCH SIMPLE ON UPDATE CASCADE ON DELETE SET NULL;