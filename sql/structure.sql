--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;


SET search_path = public, pg_catalog;

SET default_tablespace = '';

--
-- Name: contact_field_value; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_field_value (
    contact_id serial NOT NULL,
    contact_field_id integer NOT NULL,
    value text
) WITH OIDS;


--
-- Name: contact; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact (
    id serial NOT NULL,
    name character varying(255) NOT NULL
);


--
-- Name: contact_in_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_in_group (
    contact_id integer NOT NULL,
    group_id integer NOT NULL,
    operator boolean DEFAULT false NOT NULL,
    member boolean DEFAULT false NOT NULL,
    invited boolean DEFAULT false NOT NULL,
    declined_invitation boolean DEFAULT false NOT NULL,
    note text
) WITH OIDS;


--
-- Name: contact_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_group (
    id serial NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    field_group boolean DEFAULT false NOT NULL,
    date date,
    budget_code character varying(10) DEFAULT ''::character varying NOT NULL,
    system boolean DEFAULT false NOT NULL,
    mailman_address character varying(255),
    has_news boolean DEFAULT false NOT NULL,
    sticky boolean DEFAULT false NOT NULL
);


--
-- Name: choice; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE choice (
    choice_group_id integer NOT NULL,
    key character varying(255) DEFAULT ''::character varying NOT NULL,
    value character varying(255) DEFAULT ''::character varying NOT NULL
) WITH OIDS;


--
-- Name: choice_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE choice_group (
    id serial NOT NULL,
    name character varying(255),
    sort_by_key boolean DEFAULT false NOT NULL
);


--
-- Name: config; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE config (
    id character varying(32) NOT NULL,
    text text
);


--
-- Name: contact_field; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_field (
    id serial NOT NULL,
    name character varying(255) NOT NULL,
    hint text,
    type character varying(15) DEFAULT 'TEXT'::character varying NOT NULL,
    contact_group_id integer NOT NULL,
    sort_weight integer NOT NULL,
    choice_group_id integer,
    system boolean DEFAULT false NOT NULL,
    "default" text
);


--
-- Name: contact_group_news; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_group_news (
    id serial NOT NULL,
    author_id integer,
    contact_group_id integer,
    date timestamp without time zone NOT NULL,
    title text NOT NULL,
    text text NOT NULL
);


--
-- Name: contact_sysmsg; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_sysmsg (
    id serial NOT NULL,
    contact_id integer NOT NULL,
    message text NOT NULL
);


--
-- Name: group_in_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE group_in_group (
    father_id integer NOT NULL,
    subgroup_id integer NOT NULL
) WITH OIDS;


--
-- Name: COLUMN group_in_group.father_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN group_in_group.father_id IS 'Automatic member';


--
-- Name: log; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE log (
    id serial NOT NULL,
    dt timestamp without time zone NOT NULL,
    contact_id integer NOT NULL,
    action integer NOT NULL,
    target text NOT NULL,
    target_repr text NOT NULL,
    property text,
    property_repr text,
    change text
);


--
-- Name: choice_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY choice_group
    ADD CONSTRAINT choice_group_pkey PRIMARY KEY (id);


--
-- Name: choice_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY choice
    ADD CONSTRAINT choice_pkey PRIMARY KEY (choice_group_id, key);


--
-- Name: config_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY config
    ADD CONSTRAINT config_pkey PRIMARY KEY (id);


--
-- Name: contact_field_value_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY contact_field_value
    ADD CONSTRAINT contact_field_value_pkey PRIMARY KEY (contact_id, contact_field_id);


--
-- Name: contact_group_news_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY contact_group_news
    ADD CONSTRAINT contact_group_news_pkey PRIMARY KEY (id);


--
-- Name: contact_in_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY contact_in_group
    ADD CONSTRAINT contact_in_group_pkey PRIMARY KEY (contact_id, group_id);


--
-- Name: contact_name_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY contact
    ADD CONSTRAINT contact_name_key UNIQUE (name);


--
-- Name: contact_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY contact
    ADD CONSTRAINT contact_pkey PRIMARY KEY (id);


--
-- Name: contact_sysmsg_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY contact_sysmsg
    ADD CONSTRAINT contact_sysmsg_pkey PRIMARY KEY (id);


--
-- Name: group_in_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY group_in_group
    ADD CONSTRAINT group_in_group_pkey PRIMARY KEY (father_id, subgroup_id);


--
-- Name: group_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY contact_group
    ADD CONSTRAINT group_pkey PRIMARY KEY (id);


--
-- Name: log_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY log
    ADD CONSTRAINT log_pkey PRIMARY KEY (id);


--
-- Name: xfield_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY contact_field
    ADD CONSTRAINT xfield_pkey PRIMARY KEY (id);


--
-- Name: choice_choice_group_id_index; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX choice_choice_group_id_index ON choice USING btree (choice_group_id);


--
-- Name: contact_field_value_contact_field_id_index; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX contact_field_value_contact_field_id_index ON contact_field_value USING btree (contact_field_id);


--
-- Name: contact_field_value_contact_id_index; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX contact_field_value_contact_id_index ON contact_field_value USING btree (contact_id);


--
-- Name: contact_sysmsg_contact_id_idx; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX contact_sysmsg_contact_id_idx ON contact_sysmsg USING btree (contact_id);


--
-- Name: choice_choice_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY choice
    ADD CONSTRAINT choice_choice_group_id_fkey FOREIGN KEY (choice_group_id) REFERENCES choice_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: contact_field_choice_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY contact_field
    ADD CONSTRAINT contact_field_choice_group_id_fkey FOREIGN KEY (choice_group_id) REFERENCES choice_group(id) ON UPDATE CASCADE;


--
-- Name: contact_field_contact_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY contact_field
    ADD CONSTRAINT contact_field_contact_group_id_fkey FOREIGN KEY (contact_group_id) REFERENCES contact_group(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: contact_field_value_contact_field_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY contact_field_value
    ADD CONSTRAINT contact_field_value_contact_field_id_fkey FOREIGN KEY (contact_field_id) REFERENCES contact_field(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: contact_field_value_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY contact_field_value
    ADD CONSTRAINT contact_field_value_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: contact_group_news_author_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY contact_group_news
    ADD CONSTRAINT contact_group_news_author_id_fkey FOREIGN KEY (author_id) REFERENCES contact(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: contact_group_news_contact_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY contact_group_news
    ADD CONSTRAINT contact_group_news_contact_group_id_fkey FOREIGN KEY (contact_group_id) REFERENCES contact_group(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: contact_in_group_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY contact_in_group
    ADD CONSTRAINT contact_in_group_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: contact_in_group_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY contact_in_group
    ADD CONSTRAINT contact_in_group_group_id_fkey FOREIGN KEY (group_id) REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: contact_sysmsg_contact_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY contact_sysmsg
    ADD CONSTRAINT contact_sysmsg_contact_id_fkey FOREIGN KEY (contact_id) REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: group_in_group_child_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY group_in_group
    ADD CONSTRAINT group_in_group_child_group_id_fkey FOREIGN KEY (subgroup_id) REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: group_in_group_father_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY group_in_group
    ADD CONSTRAINT group_in_group_father_group_id_fkey FOREIGN KEY (father_id) REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: log_contact_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY log
    ADD CONSTRAINT log_contact_id_fk FOREIGN KEY (contact_id) REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--
