DROP FUNCTION IF EXISTS perm_c_can_see_c(integer, integer);

-- View:
-- contact_id appears in group_id
CREATE OR REPLACE VIEW v_c_appears_in_cg(contact_id, group_id) AS
    SELECT DISTINCT contact_in_group.contact_id, v_subgroups.father_id
    FROM contact_in_group
    JOIN v_subgroups ON contact_in_group.group_id=v_subgroups.child_id
    ;

-- View:
-- Can contact_id_1 see contact_id_2
-- Meaning there is a group whose members can be seen by contact_id_1 and in which is contact_id_2 is member
CREATE OR REPLACE VIEW v_c_can_see_c(contact_id_1, contact_id_2) AS
    SELECT DISTINCT v_cig_perm.contact_id AS contact_id_1, v_c_appears_in_cg.contact_id
    FROM v_cig_perm
    JOIN v_c_appears_in_cg ON v_cig_perm.group_id=v_c_appears_in_cg.group_id
    WHERE flags & 128 <> 0
    ;
