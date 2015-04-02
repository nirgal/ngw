ALTER TABLE contact_field DROP CONSTRAINT contact_field_has_choice1;
ALTER TABLE contact_field ADD CONSTRAINT contact_field_has_choice1 CHECK (
        (type<>'CHOICE' AND type<>'MULTIPLECHOICE' AND type<>'DOUBLECHOICE')
        OR choice_group_id IS NOT NULL
);
