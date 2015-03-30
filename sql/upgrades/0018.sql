-- > For each choice_group, the "best" (future) contact_field
-- SELECT choice_group.*, min(contact_field.id), count(contact_field.id)
-- FROM choice_group, contact_field 
-- WHERE choice_group.id = contact_field.choice_group_id
-- GROUP BY choice_group.id;

-- > Store it
ALTER TABLE choice_group
ADD COLUMN best_contact_field_id INTEGER;

UPDATE choice_group
SET best_contact_field_id = next_contact_field.min_contact_field_id
FROM (
	SELECT choice_group.id, min(contact_field.id) AS min_contact_field_id
	FROM choice_group, contact_field 
	WHERE choice_group.id = contact_field.choice_group_id
	GROUP BY choice_group.id
	) AS next_contact_field
WHERE choice_group.id = next_contact_field.id
;

-- UPDATE choice_group SET best_contact_field_id = NULL;

-- > List contact_field that need to be duplicated

-- SELECT contact_field.name, choice_group.name, choice_group.id AS choice_id, best_contact_field_id
-- FROM contact_field, choice_group
-- WHERE choice_group.id = contact_field.choice_group_id
-- AND choice_group.best_contact_field_id <> contact_field.id
-- ;

ALTER TABLE contact_field
ADD COLUMN duplicate_choice INTEGER;

UPDATE contact_field
SET duplicate_choice = needdup.best_contact_field_id
FROM (
	SELECT contact_field.id AS field_id, contact_field.name, choice_group.name, choice_group.id AS choice_id, best_contact_field_id
	FROM contact_field, choice_group
	WHERE choice_group.id = contact_field.choice_group_id
	AND choice_group.best_contact_field_id <> contact_field.id
) AS needdup
WHERE contact_field.id = needdup.field_id;

ALTER TABLE choice_group
DROP COLUMN best_contact_field_id;

-- Here, contact_field.duplicate_choice contains the ID of the contact_field to copy from

-- SELECT target_field.id AS for_field_id, orig_group.*
-- FROM contact_field AS orig_field
-- JOIN contact_field AS target_field ON orig_field.id = target_field.duplicate_choice
-- JOIN choice_group AS orig_group ON orig_field.choice_group_id = orig_group.id
-- ;

ALTER TABLE choice_group
ADD COLUMN for_field INTEGER;

INSERT INTO choice_group (name, sort_by_key, for_field)
SELECT *
FROM (
	SELECT orig_group.name, orig_group.sort_by_key, target_field.id
	FROM contact_field AS orig_field
	JOIN contact_field AS target_field ON orig_field.id = target_field.duplicate_choice
	JOIN choice_group AS orig_group ON orig_field.choice_group_id = orig_group.id
) AS dup;

-- Here, we duplicated the choice_group, and choice_group.for_field points to the field

INSERT INTO choice(choice_group_id, key, value)
SELECT new_choice_group.id, choice.key, choice.value
FROM choice_group 
JOIN choice ON choice_group.id = choice.choice_group_id
JOIN contact_field ON contact_field.choice_group_id = choice_group.id
JOIN choice_group AS new_choice_group ON new_choice_group.for_field = contact_field.id
;

-- Here, we duplicated the choices
-- Now update the fields to use the new choice_groups:

UPDATE contact_field
SET choice_group_id = joined.new_choice_group_id
FROM (
	SELECT contact_field.id AS field_id, contact_field.name AS field_name, choice_group.id AS new_choice_group_id
	FROM contact_field
	JOIN choice_group ON contact_field.id = choice_group.for_field
) AS joined
WHERE contact_field.id = joined.field_id;

-- Drop remaining temporary columns
ALTER TABLE contact_field DROP COLUMN duplicate_choice;
ALTER TABLE choice_group DROP COLUMN for_field;

