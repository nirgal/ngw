ALTER TABLE contact_message ADD COLUMN contact_id INTEGER;
UPDATE contact_message SET contact_id=contact_in_group.contact_id FROM contact_in_group WHERE contact_message.cig_id=contact_in_group.id;
ALTER TABLE contact_message ALTER contact_id SET NOT NULL;
ALTER TABLE contact_message ADD CONSTRAINT contact_message_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES contact(id) ON UPDATE CASCADE ON DELETE CASCADE;


ALTER TABLE contact_message ADD COLUMN group_id INTEGER;
UPDATE contact_message SET group_id=contact_in_group.group_id FROM contact_in_group WHERE contact_message.cig_id=contact_in_group.id;
ALTER TABLE contact_message ALTER group_id SET NOT NULL;
ALTER TABLE contact_message ADD CONSTRAINT contact_message_group_id_fkey FOREIGN KEY (group_id) REFERENCES contact_group(id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE contact_message DROP COLUMN cig_id;
