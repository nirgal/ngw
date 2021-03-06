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


-- That function process a flags membership & management from contact_in_group and add the missing dependent permissions.
-- For exemple, flag 'U' (can upload files) automatically grants 'e' (can see group) and 'u' (can upload file) permissions
-- See perms.py for details
CREATE OR REPLACE FUNCTION cig_add_perm_dependencies(integer) RETURNS integer
LANGUAGE SQL IMMUTABLE AS $$
    SELECT bit_or(flag) FROM (
-- 'm'ember / 'i'nvited / 'd'eclined / cancele'D'
        SELECT $1 & 15 AS flag
-- 'o'perator
        UNION (SELECT 16 WHERE $1 & (16) <> 0)
-- 'v'iewer: if v or o
        UNION (SELECT 32 WHERE $1 & (16|32) <> 0)
-- 'e'xistance: if voeEcCfFnNuUxX
        UNION (SELECT 64 WHERE $1 & (16|32|64|128|256|512|1024|2048|4096|8192|16384|32768|65536|131072) <> 0)
-- 'E': if oE
        UNION (SELECT 128 WHERE $1 & (16|128) <> 0)
-- 'c'ontent: if ovcCx
        UNION (SELECT 256 WHERE $1 & (16|32|256|512|65536) <> 0)
-- 'C': if oC
        UNION (SELECT 512 WHERE $1 & (16|512) <> 0)
-- 'f'ields: if oefF
        UNION (SELECT 1024 WHERE $1 & (16|32|1024|2048) <> 0)
-- 'F': if oF
        UNION (SELECT 2048 WHERE $1 & (16|2048) <> 0)
-- 'n'ews: if ovnN
        UNION (SELECT 4096 WHERE $1 & (16|32|4096|8192) <> 0)
-- 'N': if oN
        UNION (SELECT 8192 WHERE $1 & (16|8192) <> 0)
-- 'u'ploaded: if ovuU
        UNION (SELECT 16384 WHERE $1 & (16|32|16384|32768) <> 0)
-- 'U': if oU
        UNION (SELECT 32768 WHERE $1 & (16|32768) <> 0)
-- 'x'ternal messages: if ovxX
        UNION (SELECT 65536 WHERE $1 & (16|32|65536|131072) <> 0)
-- X: if oX
        UNION (SELECT 131072 WHERE $1 & (16|131072) <> 0)
    ) AS internal;
$$;



-- ----------------------------------------------------------------------------------------
-- Views
-- ----------------------------------------------------------------------------------------

-- View:
-- father_id is an ancestor child_id, including sub-sub.... groups
CREATE OR REPLACE VIEW v_subgroups(father_id, child_id) AS
    SELECT contact_group.id, self_and_subgroups(contact_group.id)
    FROM contact_group;

-- View:
-- contact_id is member of group_id
CREATE OR REPLACE VIEW v_c_member_of(contact_id, group_id) AS
    SELECT DISTINCT contact_in_group.contact_id, v_subgroups.father_id
    FROM contact_in_group
    JOIN v_subgroups ON contact_in_group.group_id=v_subgroups.child_id
    WHERE flags & 1 <> 0;

-- View:
-- contact_id appears in group_id
CREATE OR REPLACE VIEW v_c_appears_in_cg(contact_id, group_id) AS
    SELECT DISTINCT contact_in_group.contact_id, v_subgroups.father_id
    FROM contact_in_group
    JOIN v_subgroups ON contact_in_group.group_id=v_subgroups.child_id
    ;

-- View:
-- contact_id member/invited/declined in group_id because of a subgroups
CREATE OR REPLACE VIEW v_cig_membership_inherited(contact_id, group_id, flags) AS
    SELECT contact_in_group.contact_id, v_subgroups.father_id, bit_or(flags) & 15
    FROM contact_in_group
    JOIN v_subgroups ON contact_in_group.group_id=v_subgroups.child_id
    GROUP BY contact_in_group.contact_id, v_subgroups.father_id
    ;

-- View:
-- What 'flags' permissions does contact_id has over group_id, just because he's member of group with group_manage_group
CREATE OR REPLACE VIEW v_cig_perm_inherited_gmg(contact_id, group_id, flags) AS
    SELECT v_c_member_of.contact_id, group_manage_group.subgroup_id, cig_add_perm_dependencies(bit_or(flags))
    FROM v_c_member_of
    JOIN group_manage_group ON v_c_member_of.group_id=group_manage_group.father_id
    GROUP BY v_c_member_of.contact_id, group_manage_group.subgroup_id
    ;

-- View:
-- What 'flags' permissions does contact_id has over group_id, just because he's member of group 'admin'
CREATE OR REPLACE VIEW v_cig_perm_inherited_admin(contact_id, group_id, flags) AS
    SELECT contact.id, contact_group.id AS group_id, cig_add_perm_dependencies(16) AS flags
    FROM contact_group, contact
    JOIN v_c_member_of ON contact.id=v_c_member_of.contact_id
    WHERE v_c_member_of.group_id = 8
    ;

-- View:
-- What 'flags' permissions does contact_id has over group_id, just because he's member of group 'observer'
CREATE OR REPLACE VIEW v_cig_perm_inherited_observer(contact_id, group_id, flags) AS
    SELECT contact.id, contact_group.id AS group_id, cig_add_perm_dependencies(32) AS flags
    FROM contact_group, contact
    JOIN v_c_member_of ON contact.id=v_c_member_of.contact_id
    WHERE v_c_member_of.group_id = 9
    ;

-- View:
-- What 'flags' permissions does contact_id has over group_id?
-- Permissions are acquired though:
--  - group_mamnage_group
--  - contact_in_group (flags&~7)
--  - membership of group 'admins'
--  - membership of group 'observer'
CREATE OR REPLACE VIEW v_cig_perm(contact_id, group_id, flags) AS
    SELECT contact_id, group_id, cig_add_perm_dependencies(bit_or(flags)) FROM
    (
        SELECT contact_id, group_id, flags
        FROM v_cig_perm_inherited_gmg
        UNION
            (
            SELECT contact_in_group.contact_id, contact_in_group.group_id, flags & ~15
            FROM contact_in_group
            WHERE flags & ~15 <> 0
            )
        UNION
            (
            SELECT *
            FROM v_cig_perm_inherited_admin
            )
        UNION
            (
            SELECT *
            FROM v_cig_perm_inherited_observer
            )
    ) AS compiled
    GROUP BY contact_id, group_id
    ;

CREATE OR REPLACE VIEW v_cig_flags(contact_id, group_id, flags) AS
    SELECT contact_id, group_id, cig_add_perm_dependencies(bit_or(flags)) FROM
    (
        SELECT contact_in_group.contact_id, contact_in_group.group_id, flags
        FROM contact_in_group
        UNION
            (
            SELECT contact_id, group_id, flags
            FROM v_cig_membership_inherited
            )
        UNION (
            SELECT *
            FROM v_cig_perm_inherited_gmg
            )
        UNION
            (
            SELECT *
            FROM v_cig_perm_inherited_admin
            )
        UNION
            (
            SELECT *
            FROM v_cig_perm_inherited_observer
            )
    ) AS compiled
    GROUP by contact_id, group_id
    ;

-- View:
-- Can contact_id_1 see contact_id_2
-- Meaning there is a group whose members can be seen by contact_id_1 and in which is contact_id_2 is member
CREATE OR REPLACE VIEW v_c_can_see_c(contact_id_1, contact_id_2) AS
    SELECT DISTINCT v_cig_perm.contact_id AS contact_id_1, v_c_appears_in_cg.contact_id
    FROM v_cig_perm
    JOIN v_c_appears_in_cg ON v_cig_perm.group_id=v_c_appears_in_cg.group_id
    WHERE flags & 256 <> 0
    ;


-- List of events of contact #1 during 2017:
-- SELECT * FROM v_cig_membership_inherited JOIN contact_group ON v_cig_membership_inherited.group_id=contact_group.id WHERE contact_group.date IS NOT NULL AND daterange(contact_group.date, contact_group.end_date, '[]') && daterange('2017-01-01', '2017-12-31', '[]') AND contact_id=1;

-- Occupation of contacts during August 2017:
-- SELECT contact_id,  bit_or(flags) & 3 FROM v_cig_membership_inherited JOIN contact_group ON v_cig_membership_inherited.group_id=contact_group.id WHERE contact_group.date IS NOT NULL AND daterange(contact_group.date, contact_group.end_date, '[]') && daterange('2017-08-01', '2017-08-31', '[]') GROUP BY contact_id;

-- Availability of contacts during August 2017:
-- SELECT
-- 	contact_list.id,
-- 	COALESCE(business, 0) AS business
-- FROM (
-- 	SELECT id FROM contact
-- ) AS contact_list
-- LEFT JOIN (
-- 	SELECT contact_id,  bit_or(flags) & 3 AS business
-- 	FROM v_cig_membership_inherited
-- 	JOIN contact_group
-- 		ON v_cig_membership_inherited.group_id=contact_group.id
-- 	WHERE contact_group.date IS NOT NULL
-- 	AND daterange(contact_group.date, contact_group.end_date, '[]') && daterange('2017-08-01', '2017-08-31', '[]')
-- 	GROUP BY contact_id
-- ) AS availability
-- ON contact_list.id=availability.contact_id
-- ORDER BY contact_list.id
-- ;

-- returns the first birthday after (or equal) to start:
create or replace function birthday_after_date(birthdate date, start date) returns date as $$
declare
  d date;
begin
  /* the bith day of the year of start is */
  d = (to_char(start, 'YYYY') || '-' || to_char(birthdate, 'MM-DD'))::date;
  if d < start  /* handle end of year borner */
  then
    d = d + '1 year'::interval;
  end if;
  return d;
end;
$$ language plpgsql
immutable
returns null on null input;


-- vim: set et ts=4 ft=sql:
