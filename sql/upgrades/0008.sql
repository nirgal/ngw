-- That function process a flags membership & management from contact_in_group and add the missing dependent permissions.
-- For exemple, flag 'U' (can upload files) automatically grants 'e' (can see group) and 'u' (can upload file) permissions
-- See perms.py for details
CREATE OR REPLACE FUNCTION cig_add_perm_dependencies(integer) RETURNS integer
LANGUAGE SQL STABLE AS $$
    SELECT bit_or(flag) FROM (
-- 'm'ember / 'i'nvited / 'd'eclined
        SELECT $1 & 7 AS flag
-- 'o'perator
        UNION (SELECT 8 WHERE $1 & (8) <> 0)
-- 'v'iewer: if v or o
        UNION (SELECT 16 WHERE $1 & (8|16) <> 0)
-- 'e'xistance: if voeEcCfFnNuUxX
        UNION (SELECT 32 WHERE $1 & (8|16|32|64|128|256|512|1024|2048|4096|8192|16384|32768|65536) <> 0)
-- 'E': if oE
        UNION (SELECT 64 WHERE $1 & (8|64) <> 0)
-- 'c'ontent: if oecC
        UNION (SELECT 128 WHERE $1 & (8|16|128|256) <> 0)
-- 'C': if oC
        UNION (SELECT 256 WHERE $1 & (8|256) <> 0)
-- 'f'ields: if oefF
        UNION (SELECT 512 WHERE $1 & (8|16|512|1024) <> 0)
-- 'F': if oF
        UNION (SELECT 1024 WHERE $1 & (8|1024) <> 0)
-- 'n'ews: if oenN
        UNION (SELECT 2048 WHERE $1 & (8|16|2048|4096) <> 0)
-- 'N': if oN
        UNION (SELECT 4096 WHERE $1 & (8|4096) <> 0)
-- 'u'ploaded: if oeuU
        UNION (SELECT 8192 WHERE $1 & (8|16|8192|16384) <> 0)
-- 'U': if oU
        UNION (SELECT 16384 WHERE $1 & (8|16384) <> 0)
-- 'x'ternal messages: if oexX
        UNION (SELECT 32768 WHERE $1 & (8|16|32768|65536) <> 0)
-- X: if oX
        UNION (SELECT 65536 WHERE $1 & (8|65536) <> 0)
    ) AS internal;
$$;



-- Returns true if contact $1 is member of group $2
CREATE OR REPLACE FUNCTION c_ismemberof_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT EXISTS(
        SELECT *
        FROM contact_in_group
        WHERE contact_in_group.contact_id=contact.id
        AND contact_in_group.group_id IN (SELECT self_and_subgroups($2))
        AND flags & 1 <> 0
    ) FROM contact WHERE contact.id=$1;
$$;


-- Returns the flags of contact $1 in group $2 *without* inheriteance
CREATE OR REPLACE FUNCTION cig_flags_direct(integer, integer) RETURNS integer
LANGUAGE SQL STABLE AS $$
    SELECT COALESCE(
        (SELECT flags FROM contact_in_group WHERE contact_id=$1 AND group_id=$2),
        0);
$$;

-- Returns the membership flags (1/2/4) of contact $1 in group $2
CREATE OR REPLACE FUNCTION cig_membership(integer, integer) RETURNS integer
LANGUAGE SQL STABLE AS $$
    SELECT COALESCE(
        (SELECT bit_or(flags) & 7 AS flags
        FROM contact_in_group
        WHERE contact_id=$1 AND group_id IN (SELECT self_and_subgroups($2))),
    0);
$$;

-- Returns the inherited membership flags (1/2/4) of contact $1 in group $2
CREATE OR REPLACE FUNCTION cig_membership_inherited(integer, integer) RETURNS integer
LANGUAGE SQL STABLE AS $$
    SELECT cig_membership($1, $2) & ~cig_flags_direct($1, $2);
$$;


-- Returns the permissions flags (8/16/32...) of contact $1 in group $2
CREATE OR REPLACE FUNCTION cig_perm(integer, integer) RETURNS integer
LANGUAGE SQL STABLE AS $$
    SELECT cig_add_perm_dependencies(bit_or(admin_flags) & ~7) FROM
    (
        SELECT bit_or(gmg_perms.flags) AS admin_flags
        FROM contact_in_group
        JOIN (
            SELECT self_and_subgroups(father_id) AS group_id,
                bit_or(flags) AS flags
            FROM group_manage_group
            WHERE subgroup_id=$2
            GROUP BY group_id
        ) AS gmg_perms
        ON contact_in_group.group_id=gmg_perms.group_id
            AND contact_id = $1
            AND contact_in_group.flags & 1 <> 0
        UNION
            (
            SELECT contact_in_group.flags AS admin_flags
            FROM contact_in_group
            WHERE contact_in_group.contact_id=$1
            AND contact_in_group.group_id=$2
            )
        UNION
            (
            SELECT 8 AS admin_flags
            WHERE c_ismemberof_cg($1, 8)
            )
        UNION
            (
            SELECT 16 AS admin_flags
            WHERE c_ismemberof_cg($1, 9)
            )
        UNION
            SELECT 0
    ) AS compiled
$$;

-- Returns the inherited permissions flags (8/16/32...) of contact $1 in group $2
CREATE OR REPLACE FUNCTION cig_perm_inherited(integer, integer) RETURNS integer
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & ~cig_flags_direct($1, $2);
$$;

-- Returns the flags of contact $1 in group $2
CREATE OR REPLACE FUNCTION cig_flags(integer, integer) RETURNS integer
LANGUAGE SQL STABLE AS $$
    SELECT cig_membership($1, $2) | cig_perm($1, $2);
$$;


CREATE OR REPLACE FUNCTION perm_c_operatorof_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 8 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_viewerof_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 16 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_see_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 32 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_change_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 64 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_see_members_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 128 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_change_members_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 256 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_view_fields_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 512 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_write_fields_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 1024 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_see_news_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 2048 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_change_news_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 4096 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_see_files_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 8192 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_change_files_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 16384 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_view_msgs_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 32768 <> 0;
$$;

CREATE OR REPLACE FUNCTION perm_c_can_write_msgs_cg(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
    SELECT cig_perm($1, $2) & 65536 <> 0;
$$;


DROP FUNCTION IF EXISTS c_has_cg_permany(integer, integer, integer);
