-- From now on, can_read_messages => can_see_members
UPDATE contact_in_group SET flags = flags|128 WHERE (flags & 32768) <> 0;
UPDATE group_manage_group SET flags = flags|128 WHERE (flags & 32768) <> 0;

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
-- 'c'ontent: if oecCx
        UNION (SELECT 128 WHERE $1 & (8|16|128|256|32768) <> 0)
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
