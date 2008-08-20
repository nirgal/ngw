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

-- SELECT contact_group.id, self_and_subgroups(contact_group.id) as sg FROM contact_group;

-- SELECT * FROM contact_in_group, (SELECT contact_group.id AS joined_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree WHERE contact_in_group.group_id=group_tree.sub_group_id ORDER BY contact_id;
--  contact_id | group_id | operator | member | invited | joined_group_id | sub_group_id 
-- ------------+----------+----------+--------+---------+-----------------+--------------
--           1 |        8 | f        | t      | f       |               8 |            8
--           1 |        9 | f        | t      | f       |               9 |            9
--           1 |       35 | f        | t      | f       |              35 |           35
--           1 |       21 | f        | t      | f       |              21 |           21
--           1 |       20 | f        | t      | f       |              20 |           20
--           1 |       19 | f        | t      | f       |              19 |           19
--           1 |       34 | f        | t      | f       |              34 |           34
--           1 |       36 | f        | t      | f       |              36 |           36
--           1 |        5 | f        | t      | f       |               4 |            5
--           1 |        7 | f        | t      | f       |               5 |            7
--           1 |        7 | f        | t      | f       |               4 |            7
--           1 |        5 | f        | t      | f       |               5 |            5
--           1 |        5 | f        | t      | f       |               2 |            5
--           1 |        7 | f        | t      | f       |               7 |            7
--           1 |        7 | f        | t      | f       |               2 |            7

-- SELECT DISTINCT contact_id, contact.login, joined_group_id FROM contact_in_group JOIN contact ON (contact.id=contact_in_group.contact_id), (SELECT contact_group.id AS joined_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree WHERE contact_in_group.group_id=group_tree.sub_group_id ORDER BY contact_id;

DROP VIEW auth_user_groups;
-- CREATE VIEW auth_user_groups ( login, gid ) AS SELECT DISTINCT contact.login, joined_group_id FROM contact_in_group JOIN contact ON (contact.id=contact_in_group.contact_id), (SELECT contact_group.id AS joined_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree WHERE contact_in_group.group_id=group_tree.sub_group_id;
CREATE VIEW auth_user_groups ( login, gid ) AS SELECT DISTINCT contact.login, automatic_group_id FROM contact_in_group JOIN contact ON (contact.id=contact_in_group.contact_id), (SELECT contact_group.id AS automatic_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree WHERE contact_in_group.group_id=group_tree.sub_group_id AND contact_in_group.member;

