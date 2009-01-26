-- Rigth now, NGW can only be installed from a backup. So you'll probably never user this file
-- Make sure contrib modules _int.sql and int_aggregate.sql are loaded. See ngw README
DROP VIEW mailinginfo;
DROP VIEW auth_users_ngw;
DROP VIEW auth_users_bb;
DROP VIEW auth_users;
DROP VIEW auth_user_groups;
DROP FUNCTION self_and_subgroups(integer);
DROP FUNCTION subgroups_append(integer, integer[]);
DROP FUNCTION subgroups_append_direct(integer, integer[]);

-- $1: group id
-- $2: results
-- That function adds direct children that weren't allready members of result
-- returns a array of group id
CREATE FUNCTION subgroups_append_direct(integer, integer[]) RETURNS integer[] AS $$
    SELECT int_array_aggregate(subgroup_id) | $2 FROM group_in_group WHERE father_id=$1 AND NOT subgroup_id=ANY($2)
$$ LANGUAGE SQL STABLE;


-- $1: group id
-- $2: results
-- That function adds childrens in result array that is returned
CREATE FUNCTION subgroups_append(integer, integer[]) RETURNS SETOF integer AS $$
    SELECT int_array_enum(subgroups_append_direct($1, $2))
    UNION
    SELECT subgroups_append(subgroup_id, subgroups_append_direct($1, $2)) FROM group_in_group WHERE father_id=$1 AND NOT arraycontains($2, array[subgroup_id])
$$ LANGUAGE SQL STABLE;

-- CREATE FUNCTION self_and_subgroups(integer) RETURNS SETOF integer AS $$
--     SELECT int_array_enum(subgroups_append_2($1, '{}'::integer[]) | $1)
-- $$ LANGUAGE SQL STABLE;
CREATE FUNCTION self_and_subgroups(integer) RETURNS SETOF integer AS $$
    SELECT subgroups_append($1, '{}'::integer[])
    UNION
    SELECT $1
$$ LANGUAGE SQL STABLE;


-- select arraycontains(array[1,2,3], array[2]);
-- select array_lower('{7,8,9}'::int[], 1);
-- select array_upper('{7,8,9}'::int[], 1);
-- select ('{7,8,9}'::int[])[2];
-- select array_lower(v,1),  from (select '{7,8,9}'::int[] as v) as dummy1;
-- select array_lower(v,1),array_upper(v,1)  from (select '{7,8,9,33}'::int[]) as dummy1(v);
-- select * from generate_series(1, (select array_upper(v,1) from (select '{7,8,9,33}'::int[]) as dummy1(v)));
-- select * from int_array_enum('{7,8,9,33}'::int[]);
-- select int_array_aggregate(id) from contact_group;
-- select array[1,2,3] + array[2,6]; --> {1,2,3,2,6}
-- select array[1,2,3] | array[2,6]; --> {1,2,3,6}




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

--HS SELECT DISTINCT contact_id, contact.login, joined_group_id FROM contact_in_group JOIN contact ON (contact.id=contact_in_group.contact_id), (SELECT contact_group.id AS joined_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree WHERE contact_in_group.group_id=group_tree.sub_group_id ORDER BY contact_id;

-- CREATE VIEW auth_user_groups ( login, gid ) AS SELECT DISTINCT contact.login, joined_group_id FROM contact_in_group JOIN contact ON (contact.id=contact_in_group.contact_id), (SELECT contact_group.id AS joined_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree WHERE contact_in_group.group_id=group_tree.sub_group_id;
--CREATE VIEW auth_user_groups ( login, gid ) AS SELECT DISTINCT contact.login, automatic_group_id FROM contact_in_group JOIN contact ON (contact.id=contact_in_group.contact_id), (SELECT contact_group.id AS automatic_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree WHERE contact_in_group.group_id=group_tree.sub_group_id AND contact_in_group.member;
--
CREATE VIEW auth_user_groups ( login, gid ) AS 
    SELECT DISTINCT login_values.value, automatic_group_id
        FROM contact_in_group 
        JOIN contact_field_value AS login_values ON (login_values.contact_id=contact_in_group.contact_id AND login_values.contact_field_id=1),
        (SELECT contact_group.id AS automatic_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree
        WHERE contact_in_group.group_id=group_tree.sub_group_id AND contact_in_group.member;

CREATE VIEW auth_users (login, password) AS
    SELECT login_values.value, password_values.value
    FROM contact_field_value AS login_values
    JOIN contact_field_value AS password_values ON (login_values.contact_id=password_values.contact_id AND password_values.contact_field_id=2)
    WHERE login_values.contact_field_id=1;

CREATE VIEW auth_users_ngw (login, password) AS
    SELECT login_values.value, password_values.value
    FROM contact_field_value AS login_values
    JOIN contact_field_value AS password_values ON (login_values.contact_id=password_values.contact_id AND password_values.contact_field_id=2)
    WHERE login_values.contact_field_id=1
        AND EXISTS (SELECT * FROM auth_user_groups WHERE auth_user_groups.login=login_values.value AND auth_user_groups.gid=52);

CREATE VIEW auth_users_bb (login, password) AS
    SELECT login_values.value, password_values.value
    FROM contact_field_value AS login_values
    JOIN contact_field_value AS password_values ON (login_values.contact_id=password_values.contact_id AND password_values.contact_field_id=2)
    WHERE login_values.contact_field_id=1
        AND EXISTS (SELECT * FROM auth_user_groups WHERE auth_user_groups.login=login_values.value AND auth_user_groups.gid=53);

CREATE VIEW mailinginfo AS
    SELECT contact.id AS id, contact.name AS name, rue.value AS rue, codepostal.value AS codepostal, ville.value AS ville, pays.value AS pays, login.value AS login, password.value AS password
        FROM contact
        LEFT JOIN contact_field_value AS rue ON contact.id=rue.contact_id AND rue.contact_field_id=9
        LEFT JOIN contact_field_value AS codepostal ON contact.id=codepostal.contact_id AND codepostal.contact_field_id=11
        LEFT JOIN contact_field_value AS ville ON contact.id=ville.contact_id AND ville.contact_field_id=14
        LEFT JOIN contact_field_value AS paysid ON contact.id=paysid.contact_id AND paysid.contact_field_id=48
        LEFT JOIN choice AS pays ON pays.choice_group_id=1 AND pays.key=paysid.value
        LEFT JOIN contact_field_value AS login ON contact.id=login.contact_id AND login.contact_field_id=1
        LEFT JOIN contact_field_value AS password ON contact.id=password.contact_id AND password.contact_field_id=74
        LEFT JOIN contact_field_value AS password_status ON contact.id=password_status.contact_id AND password_status.contact_field_id=75
        WHERE password_status.value='1'
        ;

