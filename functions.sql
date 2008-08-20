
CREATE OR REPLACE FUNCTION subgroups_append(integer, integer[]) RETURNS SETOF integer AS $$
    -- Get $2 as a setof (this sucks!)
    SELECT id FROM contact_group WHERE id=ANY($2)
    UNION
    -- Add direct children
    SELECT subgroup_id FROM group_in_group WHERE father_id=$1 AND NOT subgroup_id=ANY($2)
    UNION
    -- Add all familly of direct children's
--#TODO: create function self_and_directsubgroups pour éviter l'appel récursif si un enfant est enfant de lui même!
    SELECT subgroups_append(subgroup_id, $2) FROM group_in_group WHERE father_id=$1 AND NOT subgroup_id=ANY($2)
$$ LANGUAGE SQL STABLE;

CREATE OR REPLACE FUNCTION self_and_subgroups(integer) RETURNS SETOF integer AS $$
    SELECT $1
    UNION
    SELECT subgroups_append($1, '{}'::integer[]);
$$ LANGUAGE SQL STABLE;


-- select contact_group.id, contact_group.name, array(select self_and_subgroups(id)) from contact_group;

-- admins:
-- select * from contact where exists (select * from contact_in_group where contact_id=contact.id and group_id in (select self_and_subgroups(8)));


SELECT contact.name, contact_group.name FROM contact, contact_group WHERE EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact.id and contact_in_group.group_id IN (SELECT self_and_subgroups(contact_group.id)));
