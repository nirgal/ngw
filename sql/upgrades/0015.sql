-- View:
-- contact_id member/invited/declined in group_id because of a subgroups
CREATE OR REPLACE VIEW v_cig_membership_inherited(contact_id, group_id, flags) AS
    SELECT contact_in_group.contact_id, v_subgroups.father_id, bit_or(flags) & 7
    FROM contact_in_group
    JOIN v_subgroups ON contact_in_group.group_id=v_subgroups.child_id
    GROUP BY contact_in_group.contact_id, v_subgroups.father_id
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

DROP FUNCTION IF EXISTS c_ismemberof_cg(integer,integer);
DROP FUNCTION IF EXISTS cig_flags_direct(integer, integer);
DROP FUNCTION IF EXISTS cig_membership(integer, integer);
DROP FUNCTION IF EXISTS cig_membership_inherited(integer, integer);
DROP FUNCTION IF EXISTS cig_perm(integer, integer);
DROP FUNCTION IF EXISTS cig_perm_inherited(integer, integer);
DROP FUNCTION IF EXISTS cig_flags(integer, integer);
DROP FUNCTION IF EXISTS perm_c_operatorof_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_viewerof_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_see_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_change_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_see_members_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_change_members_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_view_fields_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_write_fields_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_see_news_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_change_news_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_see_files_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_change_files_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_view_msgs_cg(integer, integer);
DROP FUNCTION IF EXISTS perm_c_can_write_msgs_cg(integer, integer);



-- vim: set et ts=4 ft=sql:
