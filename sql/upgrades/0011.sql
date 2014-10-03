CREATE OR REPLACE FUNCTION perm_c_can_see_c(integer, integer) RETURNS boolean
LANGUAGE SQL STABLE AS $$
     SELECT EXISTS(SELECT * FROM contact_group WHERE perm_c_can_see_members_cg($1, id) AND c_ismemberof_cg($2, id));
$$;
