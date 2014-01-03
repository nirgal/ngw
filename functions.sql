-- Rigth now, NGW can only be installed from a backup. So you'll probably never user this file

ALTER TABLE contact_field_value SET WITH OIDS;
ALTER TABLE contact_in_group SET WITH OIDS;
ALTER TABLE choice SET WITH OIDS;
ALTER TABLE group_in_group SET WITH OIDS;


DROP VIEW mailinginfo;
DROP VIEW auth_users_ngw;
DROP VIEW auth_users_bb;
DROP VIEW auth_users;
DROP VIEW auth_user_groups;
DROP VIEW apache_log;
DROP FUNCTION self_and_subgroups(integer);
DROP FUNCTION self_and_supergroups(integer);


-- That function returns the set of subgroups of a given group
-- Has been tested with bugus setup where A is in B and B in A.
CREATE FUNCTION self_and_subgroups(integer) RETURNS SETOF integer AS $$
    WITH RECURSIVE subgroups AS (
        -- Non-recursive term
        SELECT $1 AS self_and_subgroup
        UNION
        -- Recursive Term
        SELECT subgroup_id AS self_and_subgroup FROM group_in_group JOIN subgroups ON group_in_group.father_id=subgroups.self_and_subgroup
    )
    SELECT * FROM subgroups;
$$ LANGUAGE SQL STABLE;


-- That function returns the set of supergroups of a given group
CREATE FUNCTION self_and_supergroups(integer) RETURNS SETOF integer AS $$
    WITH RECURSIVE supergroups AS (
        -- Non-recursive term
        SELECT $1 AS self_and_supergroup
        UNION
        -- Recursive Term
        SELECT father_id AS self_and_supergroup FROM group_in_group JOIN supergroups ON group_in_group.subgroup_id=supergroups.self_and_supergroup
    )
    SELECT * FROM supergroups;
$$ LANGUAGE SQL STABLE;


-- All the groups contact #1 is member of, either directly or by inheritance:
-- SELECT DISTINCT self_and_supergroups(group_id) FROM contact_in_group WHERE contact_id=1 AND member;

-- All the groups and their subgroups:
-- SELECT contact_group.id, contact_group.name, array(select self_and_subgroups(id)) AS self_and_subgroups FROM contact_group;

-- Members of group #8:
-- select * from contact where exists (select * from contact_in_group where contact_id=contact.id and group_id in (select self_and_subgroups(8)));

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

-- This is a helper view for apache module auth_pgsql:
-- Auth_PG_log_table points to this
-- "lastconection" gets updated at each request

CREATE VIEW apache_log (login, lastconnection) AS
    SELECT login_values.value, lastconnection_values.value
    FROM contact_field_value AS login_values
    JOIN contact_field_value AS lastconnection_values ON (login_values.contact_id=lastconnection_values.contact_id AND lastconnection_values.contact_field_id=3)
    WHERE login_values.contact_field_id=1;

CREATE RULE apache_log_ins AS ON INSERT TO apache_log
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
--    EXISTS(SELECT * FROM (SELECT self_and_subgroups FROM self_and_subgroups(52)) AS user_groups JOIN contact_in_group ON user_groups.self_and_subgroups = contact_in_group.group_id AND member AND contact_in_group.contact_id=contact.id) AS is_staff,
--    EXISTS(SELECT * FROM (SELECT self_and_subgroups FROM self_and_subgroups(2)) AS user_groups JOIN contact_in_group ON user_groups.self_and_subgroups = contact_in_group.group_id AND member AND contact_in_group.contact_id=contact.id) AS is_active,
--    EXISTS(SELECT * FROM (SELECT self_and_subgroups FROM self_and_subgroups(8)) AS user_groups JOIN contact_in_group ON user_groups.self_and_subgroups = contact_in_group.group_id AND member AND contact_in_group.contact_id=contact.id) AS is_superuser,
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
