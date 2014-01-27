-- Migration script
UPDATE contact_group SET field_group=true WHERE id=52;
UPDATE contact_field SET contact_group_id=52 WHERE id=4;
UPDATE contact_field SET contact_group_id=52 WHERE id=5;

INSERT INTO contact_field (id, name, hint, type, contact_group_id, sort_weight, system)
    SELECT 83, 'Groupe par défaut', 'Identifiant du groupe qui obtient automatiquement les privilèges d''opérateur quand cet utilisateur crée un groupe.', 'NUMBER', 52, 500, true
    WHERE NOT EXISTS (SELECT * FROM contact_field WHERE id=83);
DROP FUNCTION IF EXISTS perm_c_can_change_fields_cg(integer, integer);
DELETE FROM contact_field WHERE id=74;
DROP FUNCTION IF EXISTS c_operatorof_cg(integer, integer);
DROP FUNCTION IF EXISTS c_viewerof_cg(integer, integer);




-- That function returns the set of subgroups of a given group
-- Has been tested with bugus setup where A is in B and B in A.
CREATE OR REPLACE FUNCTION self_and_subgroups(integer) RETURNS SETOF integer
LANGUAGE SQL STABLE
AS $$
    WITH RECURSIVE subgroups AS (
        -- Non-recursive term
        SELECT $1 AS self_and_subgroup
        UNION
        -- Recursive Term
        SELECT subgroup_id AS self_and_subgroup FROM group_in_group JOIN subgroups ON group_in_group.father_id=subgroups.self_and_subgroup
    )
    SELECT * FROM subgroups;
$$;


-- That function returns the set of supergroups of a given group
CREATE OR REPLACE FUNCTION self_and_supergroups(integer) RETURNS SETOF integer
LANGUAGE SQL STABLE
AS $$
    WITH RECURSIVE supergroups AS (
        -- Non-recursive term
        SELECT $1 AS self_and_supergroup
        UNION
        -- Recursive Term
        SELECT father_id AS self_and_supergroup FROM group_in_group JOIN supergroups ON group_in_group.subgroup_id=supergroups.self_and_supergroup
    )
    SELECT * FROM supergroups;
$$;


-- All the groups contact #1 is member of, either directly or by inheritance:
-- SELECT DISTINCT self_and_supergroups(group_id) FROM contact_in_group WHERE contact_id=1 AND flags & 1 <> 0;

-- All the groups and their subgroups:
-- SELECT contact_group.id, contact_group.name, array(select self_and_subgroups(id)) AS self_and_subgroups FROM contact_group;

-- Members of group #8:
-- select * from contact where exists (select * from contact_in_group where contact_id=contact.id and group_id in (select self_and_subgroups(8)) and flags & 1 <> 0);

-- SELECT contact_group.id, self_and_subgroups(contact_group.id) as sg FROM contact_group;

-- SELECT contact_id, group_id, member, invited, declined_invitation, group_tree.* FROM contact_in_group, (SELECT contact_group.id AS joined_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree WHERE contact_in_group.group_id=group_tree.sub_group_id ORDER BY contact_id;
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
--CREATE VIEW auth_user_groups ( login, gid ) AS SELECT DISTINCT contact.login, automatic_group_id FROM contact_in_group JOIN contact ON (contact.id=contact_in_group.contact_id), (SELECT contact_group.id AS automatic_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree WHERE contact_in_group.group_id=group_tree.sub_group_id AND contact_in_group.flags & 1 <> 0;
--

-- That query is used by apache module auth_pgsql to authenticate users:
CREATE OR REPLACE VIEW auth_users (login, password) AS
    SELECT login_values.value, password_values.value
    FROM contact_field_value AS login_values
    JOIN contact_field_value AS password_values ON (login_values.contact_id=password_values.contact_id AND password_values.contact_field_id=2)
    WHERE login_values.contact_field_id=1;

-- That query is used by apache module auth_pgsql to check groups:
CREATE OR REPLACE VIEW auth_user_groups ( login, gid ) AS 
    SELECT DISTINCT login_values.value, automatic_group_id
        FROM contact_in_group 
        JOIN contact_field_value AS login_values ON (login_values.contact_id=contact_in_group.contact_id AND login_values.contact_field_id=1),
        (SELECT contact_group.id AS automatic_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree
        WHERE contact_in_group.group_id=group_tree.sub_group_id AND contact_in_group.flags & 1 <> 0;

-- That query is used by apache module auth_pgsql to authenticate users in the phpbb extension:
CREATE OR REPLACE VIEW auth_users_bb (login, password) AS
    SELECT login_values.value, password_values.value
    FROM contact_field_value AS login_values
    JOIN contact_field_value AS password_values ON (login_values.contact_id=password_values.contact_id AND password_values.contact_field_id=2)
    WHERE login_values.contact_field_id=1
        AND EXISTS (SELECT * FROM auth_user_groups WHERE auth_user_groups.login=login_values.value AND auth_user_groups.gid=53);

-- This is a helper view for apache module auth_pgsql:
-- Auth_PG_log_table points to this
-- "lastconection" gets updated at each request
CREATE OR REPLACE VIEW apache_log (login, lastconnection) AS
    SELECT login_values.value, lastconnection_values.value
    FROM contact_field_value AS login_values
    JOIN contact_field_value AS lastconnection_values ON (login_values.contact_id=lastconnection_values.contact_id AND lastconnection_values.contact_field_id=3)
    WHERE login_values.contact_field_id=1;

CREATE OR REPLACE RULE apache_log_ins AS ON INSERT TO apache_log
    DO INSTEAD
    (
        -- Create lastconnection value if missing
        INSERT INTO contact_field_value
            SELECT login_values.contact_id, 3, NULL
                FROM contact_field_value AS login_values
                WHERE login_values.value = NEW.login
                AND NOT EXISTS ( 
                    SELECT *
                    FROM contact_field_value AS probe_login JOIN contact_field_value AS probe_lastconnection
                    ON (probe_login.contact_id = probe_lastconnection.contact_id AND probe_login.contact_field_id=1 AND probe_lastconnection.contact_field_id=3)
                    WHERE probe_login.value = NEW.login
                );
        -- Update lastconnection value
        UPDATE contact_field_value
            SET value = NEW.lastconnection
            WHERE contact_field_id=3
            AND contact_id = (
                SELECT login_values.contact_id FROM contact_field_value AS login_values
                WHERE login_values.value = NEW.login
                    AND login_values.contact_field_id=1);
    );



-- Create a view compatible with django.contrib.auth
--
-- CREATE OR REPLACE VIEW auth_user (id, username, first_name, last_name, email, password, is_staff, is_active, is_superuser, last_login, date_joined) AS
-- SELECT contact.id AS id,
--    login_values.value AS username,
--    contact.name AS first_name,
--    '' AS last_name,
--    email_values.value AS email,
--    'crypt$$'||password_values.value AS password,
--    EXISTS(SELECT * FROM (SELECT self_and_subgroups FROM self_and_subgroups(52)) AS user_groups JOIN contact_in_group ON user_groups.self_and_subgroups = contact_in_group.group_id AND flags & 1 <> 0 AND contact_in_group.contact_id=contact.id) AS is_staff,
--    EXISTS(SELECT * FROM (SELECT self_and_subgroups FROM self_and_subgroups(2)) AS user_groups JOIN contact_in_group ON user_groups.self_and_subgroups = contact_in_group.group_id AND flags & 1 <> 0 AND contact_in_group.contact_id=contact.id) AS is_active,
--    EXISTS(SELECT * FROM (SELECT self_and_subgroups FROM self_and_subgroups(8)) AS user_groups JOIN contact_in_group ON user_groups.self_and_subgroups = contact_in_group.group_id AND flags & 1 <> 0 AND contact_in_group.contact_id=contact.id) AS is_superuser,
--    lastconnection_values.value AS last_login,
--    '1970-01-01 00:00:00'::timestamp AS date_joined
-- FROM contact
-- JOIN contact_field_value AS login_values ON contact.id = login_values.contact_id AND login_values.contact_field_id = 1
-- LEFT JOIN contact_field_value AS email_values ON contact.id = email_values.contact_id AND email_values.contact_field_id = 7
-- JOIN contact_field_value AS password_values ON contact.id = password_values.contact_id AND password_values.contact_field_id = 2
-- LEFT JOIN contact_field_value AS lastconnection_values ON contact.id = lastconnection_values.contact_id AND lastconnection_values.contact_field_id = 3
-- ;
-- CREATE OR REPLACE RULE auth_user_upd AS ON UPDATE TO auth_user
--     DO INSTEAD
--     (
--         -- Create lastconnection value if missing
--         INSERT INTO contact_field_value
--             SELECT NEW.id, 3, NULL
--                 WHERE NOT EXISTS ( 
--                     SELECT *
--                     FROM contact_field_value AS probe
--                     WHERE probe.contact_id = NEW.id
--                     AND probe.contact_field_id=3);
--         -- Update lastconnection value
--         UPDATE contact_field_value
--             SET value = NEW.last_login
--             WHERE contact_field_id=3
--             AND contact_id = NEW.id;
--         -- TODO: raise if other value changed
--     );



CREATE OR REPLACE FUNCTION c_ismemberof_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT EXISTS(SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=contact.id AND contact_in_group.group_id IN (SELECT self_and_subgroups($2)) AND flags & 1 <> 0) FROM contact WHERE contact.id=$1;
$$;


-- C "operates" group CG with at least one of the flags if:
-- * He directly has a matching flag in group
-- * He is a member (flag1), either directly or indirectly, of a group that has a matching flag priviledge
CREATE OR REPLACE FUNCTION c_has_cg_permany(integer, integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT
    EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=$1 AND contact_in_group.group_id=$2 AND flags & $3 <> 0)
    OR
    EXISTS (SELECT * FROM contact_in_group WHERE contact_in_group.contact_id=$1 AND group_id IN (SELECT self_and_subgroups(father_id) FROM group_manage_group WHERE subgroup_id=$2 AND group_manage_group.flags & $3 <> 0) AND contact_in_group.flags & 1 <> 0);
$$;


-- See core/perms.py for a full description of these functions:

CREATE OR REPLACE FUNCTION perm_c_operatorof_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR  c_has_cg_permany($1, $2, 8);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_see_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_ismemberof_cg($1, 9) OR c_has_cg_permany($1, $2, 8|16|32|64|128|256|512|1024|2048|4096|8192|16384);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_change_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_has_cg_permany($1, $2, 8|64);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_see_members_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_ismemberof_cg($1, 9) OR c_has_cg_permany($1, $2, 8|16|128|256);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_change_members_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_has_cg_permany($1, $2, 8|256);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_view_fields_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_ismemberof_cg($1, 9) OR c_has_cg_permany($1, $2, 8|16|512|1024);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_write_fields_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_has_cg_permany($1, $2, 8|1024);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_see_news_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_ismemberof_cg($1, 9) OR c_has_cg_permany($1, $2, 8|16|2048|4096);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_change_news_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_has_cg_permany($1, $2, 8|4096);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_see_files_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_ismemberof_cg($1, 9) OR c_has_cg_permany($1, $2, 8|16|8192|16384);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_change_files_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_has_cg_permany($1, $2, 8|16384);
$$;


--  Get the list of groups whose member can be seen by contact cid:

-- CREATE OR REPLACE FUNCTION perm_c_can_see_c(integer, integer) RETURNS boolean
-- LANGUAGE SQL STABLE AS $$
--     SELECT EXISTS( c_ismemberof_cg($1, 8) OR c_ismemberof_cg($1, 9) OR ;
-- $$;

