-- Migration script
-- DROP FUNCTION IF EXISTS c_operatorof_cg(integer, integer);
-- DROP FUNCTION IF EXISTS c_viewerof_cg(integer, integer);
-- DROP VIEW IF EXISTS auth_users;
-- DROP VIEW IF EXISTS apache_log;
-- DROP VIEW IF EXISTS auth_users_bb;
-- DROP TABLE IF EXISTS contact_sysmsg;
-- UPDATE contact_field_value SET value='crypt$$'||value WHERE contact_field_id=2 AND value NOT LIKE '%$%';
-- ALTER TABLE contact_in_group DROP CONSTRAINT contact_in_group_pkey;
-- ALTER TABLE contact_in_group ADD COLUMN id SERIAL NOT NULL PRIMARY KEY;
-- ALTER TABLE contact_in_group SET WITHOUT OIDS;
CREATE TABLE IF NOT EXISTS contact_message (
    id serial NOT NULL PRIMARY KEY,
    cig_id integer NOT NULL REFERENCES contact_in_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    send_date timestamp without time zone NOT NULL,
    read_date timestamp without time zone,
    is_answer boolean DEFAULT false NOT NULL,
    text text,
    sync_info text
);
ALTER TABLE contact_group DROP COLUMN IF EXISTS has_news;

SET TIMEZONE TO UTC;
ALTER TABLE contact_group_news ALTER COLUMN "date" TYPE timestamp with time zone;
ALTER TABLE contact_message ALTER COLUMN send_date TYPE timestamp with time zone;
ALTER TABLE contact_message ALTER COLUMN read_date TYPE timestamp with time zone;
ALTER TABLE contact_group ALTER COLUMN "date" TYPE timestamp with time zone;
DROP SEQUENCE IF EXISTS contact_field_value_contact_id_seq CASCADE;

UPDATE contact_in_group SET flags = flags|32768|65536 WHERE (flags & 8) <> 0;
UPDATE contact_in_group SET flags = flags|32768 WHERE (flags & 16) <> 0;
UPDATE group_manage_group SET flags = flags|32768|65536 WHERE (flags & 8) <> 0;
UPDATE group_manage_group SET flags = flags|32768 WHERE (flags & 16) <> 0;

SET TIMEZONE TO UTC;
ALTER TABLE contact_group ALTER COLUMN "date" TYPE date;
ALTER TABLE log  ALTER COLUMN "dt" TYPE timestamp with time zone;
-- End migration script




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
-- CREATE OR REPLACE VIEW auth_users (login, password) AS
--     SELECT login_values.value, password_values.value
--     FROM contact_field_value AS login_values
--     JOIN contact_field_value AS password_values ON (login_values.contact_id=password_values.contact_id AND password_values.contact_field_id=2)
--     WHERE login_values.contact_field_id=1;

-- That query is used by apache module auth_pgsql to check groups:
-- CREATE OR REPLACE VIEW auth_user_groups ( login, gid ) AS 
--     SELECT DISTINCT login_values.value, automatic_group_id
--         FROM contact_in_group 
--         JOIN contact_field_value AS login_values ON (login_values.contact_id=contact_in_group.contact_id AND login_values.contact_field_id=1),
--         (SELECT contact_group.id AS automatic_group_id, self_and_subgroups(contact_group.id) as sub_group_id FROM contact_group) AS group_tree
--         WHERE contact_in_group.group_id=group_tree.sub_group_id AND contact_in_group.flags & 1 <> 0;

-- That query is used by apache module auth_pgsql to authenticate users in the phpbb extension:
--CREATE OR REPLACE VIEW auth_users_bb (login, password) AS
--    SELECT login_values.value, password_values.value
--    FROM contact_field_value AS login_values
--    JOIN contact_field_value AS password_values ON (login_values.contact_id=password_values.contact_id AND password_values.contact_field_id=2)
--    WHERE login_values.contact_field_id=1
--        AND EXISTS (SELECT * FROM auth_user_groups WHERE auth_user_groups.login=login_values.value AND auth_user_groups.gid=53);

-- This is a helper view for apache module auth_pgsql:
-- Auth_PG_log_table points to this
-- "lastconection" gets updated at each request
-- CREATE OR REPLACE VIEW apache_log (login, lastconnection) AS
--     SELECT login_values.value, lastconnection_values.value
--     FROM contact_field_value AS login_values
--     JOIN contact_field_value AS lastconnection_values ON (login_values.contact_id=lastconnection_values.contact_id AND lastconnection_values.contact_field_id=3)
--     WHERE login_values.contact_field_id=1;
-- 
-- CREATE OR REPLACE RULE apache_log_ins AS ON INSERT TO apache_log
--     DO INSTEAD
--     (
--         -- Create lastconnection value if missing
--         INSERT INTO contact_field_value
--             SELECT login_values.contact_id, 3, NULL
--                 FROM contact_field_value AS login_values
--                 WHERE login_values.value = NEW.login
--                 AND NOT EXISTS ( 
--                     SELECT *
--                     FROM contact_field_value AS probe_login JOIN contact_field_value AS probe_lastconnection
--                     ON (probe_login.contact_id = probe_lastconnection.contact_id AND probe_login.contact_field_id=1 AND probe_lastconnection.contact_field_id=3)
--                     WHERE probe_login.value = NEW.login
--                 );
--         -- Update lastconnection value
--         UPDATE contact_field_value
--             SET value = NEW.lastconnection
--             WHERE contact_field_id=3
--             AND contact_id = (
--                 SELECT login_values.contact_id FROM contact_field_value AS login_values
--                 WHERE login_values.value = NEW.login
--                     AND login_values.contact_field_id=1);
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
    SELECT c_ismemberof_cg($1, 8) OR c_ismemberof_cg($1, 9) OR c_has_cg_permany($1, $2, 8|16|32|64|128|256|512|1024|2048|4096|8192|16384|32768|65536);
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

CREATE OR REPLACE FUNCTION perm_c_can_view_msgs_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_ismemberof_cg($1, 9) OR c_has_cg_permany($1, $2, 8|16|32768|65536);
$$;

CREATE OR REPLACE FUNCTION perm_c_can_write_msgs_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT c_ismemberof_cg($1, 8) OR c_has_cg_permany($1, $2, 8|65536);
$$;


--  Get the list of groups whose member can be seen by contact cid:

-- CREATE OR REPLACE FUNCTION perm_c_can_see_c(integer, integer) RETURNS boolean
-- LANGUAGE SQL STABLE AS $$
--     SELECT EXISTS( c_ismemberof_cg($1, 8) OR c_ismemberof_cg($1, 9) OR ;
-- $$;

