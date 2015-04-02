ALTER TABLE contact_field ADD CONSTRAINT contact_field_has_choice1 CHECK (
        (type<>'choice' AND type<>'MULTIPLECHOICE' AND type<>'DOUBLECHOICE')
        OR choice_group_id IS NOT NULL
);
ALTER TABLE contact_field ADD CONSTRAINT contact_field_has_choice2 CHECK (
        type<>'DOUBLECHOICE'
        OR choice_group2_id IS NOT NULL
);
