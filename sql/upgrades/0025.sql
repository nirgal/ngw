-- indexes from old syncdb

DROP INDEX IF EXISTS choice_choice_group_id;
DROP INDEX IF EXISTS config_id_like;
DROP INDEX IF EXISTS contact_field_choice_group2_id;
DROP INDEX IF EXISTS contact_field_choice_group_id;
DROP INDEX IF EXISTS contact_field_contact_group_id;
DROP INDEX IF EXISTS contact_field_value_contact_field_id;
DROP INDEX IF EXISTS contact_field_value_contact_id;
DROP INDEX IF EXISTS contact_group_news_author_id;
DROP INDEX IF EXISTS contact_group_news_contact_group_id;
DROP INDEX IF EXISTS contact_in_group_contact_id;
DROP INDEX IF EXISTS contact_in_group_group_id;
DROP INDEX IF EXISTS contact_message_contact_id;
DROP INDEX IF EXISTS contact_message_group_id;
DROP INDEX IF EXISTS contact_message_read_by_id;
DROP INDEX IF EXISTS contact_name_like;
DROP INDEX IF EXISTS group_in_group_father_id;
DROP INDEX IF EXISTS group_in_group_subgroup_id;
DROP INDEX IF EXISTS group_manage_group_father_id;
DROP INDEX IF EXISTS group_manage_group_subgroup_id;
DROP INDEX IF EXISTS log_contact_id;

-- indexes from old backup

DROP INDEX IF EXISTS auth_group_name_like;
DROP INDEX IF EXISTS auth_group_permissions_group_id;
DROP INDEX IF EXISTS auth_group_permissions_permission_id;
DROP INDEX IF EXISTS auth_permission_content_type_id;
DROP INDEX IF EXISTS choice_choice_group_id;
DROP INDEX IF EXISTS config_id_like;
DROP INDEX IF EXISTS contact_field_choice_group2_id;
DROP INDEX IF EXISTS contact_field_choice_group_id;
DROP INDEX IF EXISTS contact_field_contact_group_id;
DROP INDEX IF EXISTS contact_field_value_contact_field_id;
DROP INDEX IF EXISTS contact_field_value_contact_id;
DROP INDEX IF EXISTS contact_group_news_author_id;
DROP INDEX IF EXISTS contact_group_news_contact_group_id;
DROP INDEX IF EXISTS contact_in_group_contact_id;
DROP INDEX IF EXISTS contact_in_group_group_id;
DROP INDEX IF EXISTS contact_message_contact_id;
DROP INDEX IF EXISTS contact_message_group_id;
DROP INDEX IF EXISTS contact_message_read_by_id;
DROP INDEX IF EXISTS contact_name_like;
DROP INDEX IF EXISTS django_admin_log_content_type_id;
DROP INDEX IF EXISTS django_admin_log_user_id;
DROP INDEX IF EXISTS django_session_expire_date;
DROP INDEX IF EXISTS django_session_session_key_like;
DROP INDEX IF EXISTS group_in_group_father_id;
DROP INDEX IF EXISTS group_in_group_subgroup_id;
DROP INDEX IF EXISTS group_manage_group_father_id;
DROP INDEX IF EXISTS group_manage_group_subgroup_id;
DROP INDEX IF EXISTS log_contact_id;

-- contrainsts from old syncdb

ALTER TABLE ONLY choice DROP CONSTRAINT IF EXISTS choice_choice_group_id_key_key CASCADE;
-- ALTER TABLE ONLY choice_group DROP CONSTRAINT IF EXISTS choice_group_pkey CASCADE;
-- ALTER TABLE ONLY choice DROP CONSTRAINT IF EXISTS choice_pkey CASCADE;
-- ALTER TABLE ONLY config DROP CONSTRAINT IF EXISTS config_pkey CASCADE;
-- ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS contact_field_pkey CASCADE;
ALTER TABLE ONLY contact_field_value DROP CONSTRAINT IF EXISTS contact_field_value_contact_id_contact_field_id_key CASCADE;
-- ALTER TABLE ONLY contact_field_value DROP CONSTRAINT IF EXISTS contact_field_value_pkey CASCADE;
-- ALTER TABLE ONLY contact_group_news DROP CONSTRAINT IF EXISTS contact_group_news_pkey CASCADE;
-- ALTER TABLE ONLY contact_group DROP CONSTRAINT IF EXISTS contact_group_pkey CASCADE;
-- ALTER TABLE ONLY contact_in_group DROP CONSTRAINT IF EXISTS contact_in_group_pkey CASCADE;
-- ALTER TABLE ONLY contact_message DROP CONSTRAINT IF EXISTS contact_message_pkey CASCADE;
ALTER TABLE ONLY contact DROP CONSTRAINT IF EXISTS contact_name_key CASCADE;
-- ALTER TABLE ONLY contact DROP CONSTRAINT IF EXISTS contact_pkey CASCADE;
ALTER TABLE ONLY group_in_group DROP CONSTRAINT IF EXISTS group_in_group_father_id_subgroup_id_key CASCADE;
-- ALTER TABLE ONLY group_in_group DROP CONSTRAINT IF EXISTS group_in_group_pkey CASCADE;
ALTER TABLE ONLY group_manage_group DROP CONSTRAINT IF EXISTS group_manage_group_father_id_subgroup_id_key CASCADE;
-- ALTER TABLE ONLY group_manage_group DROP CONSTRAINT IF EXISTS group_manage_group_pkey CASCADE;
-- ALTER TABLE ONLY log DROP CONSTRAINT IF EXISTS log_pkey CASCADE;
ALTER TABLE ONLY choice DROP CONSTRAINT IF EXISTS choice_choice_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS contact_field_choice_group2_id_fkey CASCADE;
ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS contact_field_choice_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS contact_field_contact_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_field_value DROP CONSTRAINT IF EXISTS contact_field_value_contact_field_id_fkey CASCADE;
ALTER TABLE ONLY contact_field_value DROP CONSTRAINT IF EXISTS contact_field_value_contact_id_fkey CASCADE;
ALTER TABLE ONLY contact_group_news DROP CONSTRAINT IF EXISTS contact_group_news_author_id_fkey CASCADE;
ALTER TABLE ONLY contact_group_news DROP CONSTRAINT IF EXISTS contact_group_news_contact_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_in_group DROP CONSTRAINT IF EXISTS contact_in_group_contact_id_fkey CASCADE;
ALTER TABLE ONLY contact_in_group DROP CONSTRAINT IF EXISTS contact_in_group_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_message DROP CONSTRAINT IF EXISTS contact_message_contact_id_fkey CASCADE;
ALTER TABLE ONLY contact_message DROP CONSTRAINT IF EXISTS contact_message_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_message DROP CONSTRAINT IF EXISTS contact_message_read_by_id_fkey CASCADE;
ALTER TABLE ONLY group_in_group DROP CONSTRAINT IF EXISTS group_in_group_father_id_fkey CASCADE;
ALTER TABLE ONLY group_in_group DROP CONSTRAINT IF EXISTS group_in_group_subgroup_id_fkey CASCADE;
ALTER TABLE ONLY group_manage_group DROP CONSTRAINT IF EXISTS group_manage_group_father_id_fkey CASCADE;
ALTER TABLE ONLY group_manage_group DROP CONSTRAINT IF EXISTS group_manage_group_subgroup_id_fkey CASCADE;
ALTER TABLE ONLY log DROP CONSTRAINT IF EXISTS log_contact_id_fkey CASCADE;


-- contrainsts from old backups

-- ALTER TABLE ONLY choice_group DROP CONSTRAINT IF EXISTS choice_group_pkey CASCADE;
-- ALTER TABLE ONLY choice DROP CONSTRAINT IF EXISTS choice_pkey CASCADE;
-- ALTER TABLE ONLY config DROP CONSTRAINT IF EXISTS config_pkey CASCADE;
-- ALTER TABLE ONLY contact_field_value DROP CONSTRAINT IF EXISTS contact_field_value_pkey CASCADE;
-- ALTER TABLE ONLY contact_group_news DROP CONSTRAINT IF EXISTS contact_group_news_pkey CASCADE;
-- ALTER TABLE ONLY contact_in_group DROP CONSTRAINT IF EXISTS contact_in_group_pkey CASCADE;
-- ALTER TABLE ONLY contact_message DROP CONSTRAINT IF EXISTS contact_message_pkey CASCADE;
ALTER TABLE ONLY contact DROP CONSTRAINT IF EXISTS contact_name_key CASCADE;
-- ALTER TABLE ONLY contact DROP CONSTRAINT IF EXISTS contact_pkey CASCADE;
-- ALTER TABLE ONLY group_in_group DROP CONSTRAINT IF EXISTS group_in_group_pkey CASCADE;
-- ALTER TABLE ONLY group_manage_group DROP CONSTRAINT IF EXISTS group_manage_group_pkey CASCADE;
-- ALTER TABLE ONLY contact_group DROP CONSTRAINT IF EXISTS group_pkey CASCADE;
-- ALTER TABLE ONLY log DROP CONSTRAINT IF EXISTS log_pkey CASCADE;
-- ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS xfield_pkey CASCADE;
ALTER TABLE ONLY choice DROP CONSTRAINT IF EXISTS choice_choice_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS contact_field_choice_group2_id_fkey CASCADE;
ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS contact_field_choice_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS contact_field_contact_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_field_value DROP CONSTRAINT IF EXISTS contact_field_value_contact_field_id_fkey CASCADE;
ALTER TABLE ONLY contact_field_value DROP CONSTRAINT IF EXISTS contact_field_value_contact_id_fkey CASCADE;
ALTER TABLE ONLY contact_group_news DROP CONSTRAINT IF EXISTS contact_group_news_author_id_fkey CASCADE;
ALTER TABLE ONLY contact_group_news DROP CONSTRAINT IF EXISTS contact_group_news_contact_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_in_group DROP CONSTRAINT IF EXISTS contact_in_group_contact_id_fkey CASCADE;
ALTER TABLE ONLY contact_in_group DROP CONSTRAINT IF EXISTS contact_in_group_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_message DROP CONSTRAINT IF EXISTS contact_message_contact_id_fkey CASCADE;
ALTER TABLE ONLY contact_message DROP CONSTRAINT IF EXISTS contact_message_group_id_fkey CASCADE;
ALTER TABLE ONLY contact_message DROP CONSTRAINT IF EXISTS contact_message_read_by_id_fkey CASCADE;
ALTER TABLE ONLY group_in_group DROP CONSTRAINT IF EXISTS group_in_group_child_group_id_fkey CASCADE;
ALTER TABLE ONLY group_in_group DROP CONSTRAINT IF EXISTS group_in_group_father_group_id_fkey CASCADE;
ALTER TABLE ONLY group_manage_group DROP CONSTRAINT IF EXISTS group_manage_group_father_id_fkey CASCADE;
ALTER TABLE ONLY group_manage_group DROP CONSTRAINT IF EXISTS group_manage_group_subgroup_id_fkey CASCADE;
ALTER TABLE ONLY log DROP CONSTRAINT IF EXISTS log_contact_id_fk CASCADE;

-- contrainsts from structure.sql

ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS contact_field_has_choice1;
ALTER TABLE ONLY contact_field DROP CONSTRAINT IF EXISTS contact_field_has_choice2;

-- Create the indexes & constraints as they are generated by the migrations framework

CREATE INDEX "choice_choice_group_id_2563ec9f716ed7f_idx" ON "choice" ("choice_group_id", "key");
CREATE INDEX "choice_f4b0db67" ON "choice" ("choice_group_id");
CREATE INDEX "config_id_7156131b6f87a72e_like" ON "config" ("id" varchar_pattern_ops);
CREATE INDEX "contact_field_1228c760" ON "contact_field" ("choice_group2_id");
CREATE INDEX "contact_field_83bee628" ON "contact_field" ("contact_group_id");
CREATE INDEX "contact_field_f4b0db67" ON "contact_field" ("choice_group_id");
CREATE INDEX "contact_field_value_6d82f13d" ON "contact_field_value" ("contact_id");
CREATE INDEX "contact_field_value_9ff6aeda" ON "contact_field_value" ("contact_field_id");
CREATE INDEX "contact_field_value_contact_id_6612d749275a0aff_idx" ON "contact_field_value" ("contact_id", "contact_field_id");
CREATE INDEX "contact_group_news_4f331e2f" ON "contact_group_news" ("author_id");
CREATE INDEX "contact_group_news_83bee628" ON "contact_group_news" ("contact_group_id");
CREATE INDEX "contact_in_group_0e939a4f" ON "contact_in_group" ("group_id");
CREATE INDEX "contact_in_group_6d82f13d" ON "contact_in_group" ("contact_id");
CREATE INDEX "contact_message_066e88bf" ON "contact_message" ("read_by_id");
CREATE INDEX "contact_message_0e939a4f" ON "contact_message" ("group_id");
CREATE INDEX "contact_message_6d82f13d" ON "contact_message" ("contact_id");
CREATE INDEX "contact_name_49dd4eef6c8ac10c_like" ON "contact" ("name" varchar_pattern_ops);
CREATE INDEX "group_in_group_4138be47" ON "group_in_group" ("father_id");
CREATE INDEX "group_in_group_cd51192c" ON "group_in_group" ("subgroup_id");
CREATE INDEX "group_in_group_father_id_7f6757e9670d5f7_idx" ON "group_in_group" ("father_id", "subgroup_id");
CREATE INDEX "group_manage_group_4138be47" ON "group_manage_group" ("father_id");
CREATE INDEX "group_manage_group_cd51192c" ON "group_manage_group" ("subgroup_id");
CREATE INDEX "group_manage_group_father_id_52a5dc856a199e85_idx" ON "group_manage_group" ("father_id", "subgroup_id");
CREATE INDEX "log_6d82f13d" ON "log" ("contact_id");

-- Recreate other constraints

ALTER TABLE "choice" ADD CONSTRAINT "choice_choice_group_id_2563ec9f716ed7f_uniq" UNIQUE ("choice_group_id", "key");
ALTER TABLE "choice" ADD CONSTRAINT "choice_choice_group_id_4568cbac38e4b621_fk_choice_group_id" FOREIGN KEY ("choice_group_id") REFERENCES "choice_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_field" ADD CONSTRAINT "contact_f_contact_group_id_253b0c50ea39cbd3_fk_contact_group_id" FOREIGN KEY ("contact_group_id") REFERENCES "contact_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_field" ADD CONSTRAINT "contact_fi_choice_group2_id_46884c2baaf6ec75_fk_choice_group_id" FOREIGN KEY ("choice_group2_id") REFERENCES "choice_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_field" ADD CONSTRAINT "contact_fie_choice_group_id_74a8c583e1609227_fk_choice_group_id" FOREIGN KEY ("choice_group_id") REFERENCES "choice_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_field_value" ADD CONSTRAINT "contact_f_contact_field_id_2e1a8e724ee18bfb_fk_contact_field_id" FOREIGN KEY ("contact_field_id") REFERENCES "contact_field" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_field_value" ADD CONSTRAINT "contact_field_value_contact_id_447b8d296065db64_fk_contact_id" FOREIGN KEY ("contact_id") REFERENCES "contact" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_field_value" ADD CONSTRAINT "contact_field_value_contact_id_6612d749275a0aff_uniq" UNIQUE ("contact_id", "contact_field_id");
ALTER TABLE "contact_group_news" ADD CONSTRAINT "contact_g_contact_group_id_13b75ad953503203_fk_contact_group_id" FOREIGN KEY ("contact_group_id") REFERENCES "contact_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_group_news" ADD CONSTRAINT "contact_group_news_author_id_2015ba67ddc77c7a_fk_contact_id" FOREIGN KEY ("author_id") REFERENCES "contact" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_in_group" ADD CONSTRAINT "contact_in_group_contact_id_51c1cce7095ded68_fk_contact_id" FOREIGN KEY ("contact_id") REFERENCES "contact" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_in_group" ADD CONSTRAINT "contact_in_group_group_id_702de272d35c3c93_fk_contact_group_id" FOREIGN KEY ("group_id") REFERENCES "contact_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_message" ADD CONSTRAINT "contact_message_contact_id_798bdb0be19ca8a2_fk_contact_id" FOREIGN KEY ("contact_id") REFERENCES "contact" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_message" ADD CONSTRAINT "contact_message_group_id_12cb02ee503d4fcd_fk_contact_group_id" FOREIGN KEY ("group_id") REFERENCES "contact_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "contact_message" ADD CONSTRAINT "contact_message_read_by_id_6f667431377ae8f_fk_contact_id" FOREIGN KEY ("read_by_id") REFERENCES "contact" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "group_in_group" ADD CONSTRAINT "group_in_group_father_id_51ea881877515451_fk_contact_group_id" FOREIGN KEY ("father_id") REFERENCES "contact_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "group_in_group" ADD CONSTRAINT "group_in_group_father_id_7f6757e9670d5f7_uniq" UNIQUE ("father_id", "subgroup_id");
ALTER TABLE "group_in_group" ADD CONSTRAINT "group_in_group_subgroup_id_60588f82024917b5_fk_contact_group_id" FOREIGN KEY ("subgroup_id") REFERENCES "contact_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "group_manage_group" ADD CONSTRAINT "group_manage_gro_father_id_29893d52ed2bf4fd_fk_contact_group_id" FOREIGN KEY ("father_id") REFERENCES "contact_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "group_manage_group" ADD CONSTRAINT "group_manage_group_father_id_52a5dc856a199e85_uniq" UNIQUE ("father_id", "subgroup_id");
ALTER TABLE "group_manage_group" ADD CONSTRAINT "group_manage_g_subgroup_id_5ed5901f4c1870d9_fk_contact_group_id" FOREIGN KEY ("subgroup_id") REFERENCES "contact_group" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "log" ADD CONSTRAINT "log_contact_id_62fd9154c6632c6e_fk_contact_id" FOREIGN KEY ("contact_id") REFERENCES "contact" ("id") DEFERRABLE INITIALLY DEFERRED;


-- This is equivalent to a migration:

INSERT INTO django_migrations (app, name, applied)
VALUES('ngw', '0001_initial', now());
