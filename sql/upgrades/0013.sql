DROP FUNCTION IF EXISTS perm_c_can_see_c(integer, integer);

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
    SELECT contact.id, contact_group.id AS group_id, cig_add_perm_dependencies(8) AS flags
    FROM contact_group, contact
    JOIN v_c_member_of ON contact.id=v_c_member_of.contact_id
    WHERE v_c_member_of.group_id = 8
    ;

-- View:
-- What 'flags' permissions does contact_id has over group_id, just because he's member of group 'observer'
CREATE OR REPLACE VIEW v_cig_perm_inherited_observer(contact_id, group_id, flags) AS
    SELECT contact.id, contact_group.id AS group_id, cig_add_perm_dependencies(16) AS flags
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
            SELECT contact_in_group.contact_id, contact_in_group.group_id, flags & ~7
            FROM contact_in_group
            WHERE flags & ~7 <> 0
            )
        UNION
            (
            SELECT *
            FROM v_cig_perm_inherited_admin
            )
        UNION
            (
            SELECT * FROM v_cig_perm_inherited_observer
            )
    ) AS compiled
    GROUP BY contact_id, group_id
    ;
      

-- View:
-- Can contact_id_1 see contact_id_2
-- Meaning there is a group whose members can be seen by contact_id_1 and in which is contact_id_2 is member
CREATE OR REPLACE VIEW v_c_can_see_c(contact_id_1, contact_id_2) AS
    SELECT DISTINCT v_cig_perm.contact_id AS contact_id_1, v_c_member_of.contact_id
    FROM v_cig_perm
    JOIN v_c_member_of ON v_cig_perm.group_id=v_c_member_of.group_id
    WHERE flags & 128 <> 0
    ;

