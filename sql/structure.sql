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
-- Name: config; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE config (
    id character varying(32) NOT NULL PRIMARY KEY,
    text text
);


--
-- Name: contact; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact (
    id serial NOT NULL PRIMARY KEY,
    name character varying(255) NOT NULL UNIQUE
);


--
-- Name: contact_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_group (
    id serial NOT NULL PRIMARY KEY,
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
-- Name: choice_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE choice_group (
    id serial NOT NULL PRIMARY KEY,
    name character varying(255),
    sort_by_key boolean DEFAULT false NOT NULL
);


--
-- Name: choice; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE choice (
    choice_group_id integer NOT NULL REFERENCES choice_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    key character varying(255) DEFAULT ''::character varying NOT NULL,
    value character varying(255) DEFAULT ''::character varying NOT NULL,
    PRIMARY KEY (choice_group_id, key)
) WITH OIDS;


--
-- Name: choice_choice_group_id_index; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX choice_choice_group_id_index ON choice USING btree (choice_group_id);


--
-- Name: contact_field; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_field (
    id serial NOT NULL PRIMARY KEY,
    name character varying(255) NOT NULL,
    hint text,
    type character varying(15) DEFAULT 'TEXT'::character varying NOT NULL,
    contact_group_id integer NOT NULL REFERENCES contact_group(id) ON UPDATE CASCADE ON DELETE CASCADE,
    sort_weight integer NOT NULL,
    choice_group_id integer REFERENCES choice_group(id) ON UPDATE CASCADE,
    system boolean DEFAULT false NOT NULL,
    "default" text
);


--
-- Name: contact_field_value; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_field_value (
    contact_id serial NOT NULL REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    contact_field_id integer NOT NULL REFERENCES contact_field(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    value text,
    PRIMARY KEY (contact_id, contact_field_id)
) WITH OIDS;


--
-- Name: contact_field_value_contact_field_id_index; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX contact_field_value_contact_field_id_index ON contact_field_value USING btree (contact_field_id);


--
-- Name: contact_field_value_contact_id_index; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX contact_field_value_contact_id_index ON contact_field_value USING btree (contact_id);


--
-- Name: contact_in_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_in_group (
    contact_id integer NOT NULL REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    group_id integer NOT NULL REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    operator boolean DEFAULT false NOT NULL,
    viewer boolean DEFAULT false NOT NULL,
    member boolean DEFAULT false NOT NULL,
    invited boolean DEFAULT false NOT NULL,
    declined_invitation boolean DEFAULT false NOT NULL,
    note text,
    PRIMARY KEY (contact_id, group_id)
) WITH OIDS;
-- ALTER TABLE contact_in_group ADD COLUMN viewer boolean DEFAULT false NOT NULL;


--
-- Name: contact_group_news; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_group_news (
    id serial NOT NULL PRIMARY KEY,
    author_id integer REFERENCES contact(id) ON UPDATE CASCADE ON DELETE CASCADE,
    contact_group_id integer REFERENCES contact_group(id) ON UPDATE CASCADE ON DELETE CASCADE,
    date timestamp without time zone NOT NULL,
    title text NOT NULL,
    text text NOT NULL
);


--
-- Name: contact_sysmsg; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_sysmsg (
    id serial NOT NULL PRIMARY KEY,
    contact_id integer NOT NULL REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    message text NOT NULL
);


--
-- Name: contact_sysmsg_contact_id_idx; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX contact_sysmsg_contact_id_idx ON contact_sysmsg USING btree (contact_id);


--
-- Name: group_in_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE group_in_group (
    father_id integer NOT NULL REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    subgroup_id integer NOT NULL REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (father_id, subgroup_id)
) WITH OIDS;


--
-- Name: COLUMN group_in_group.father_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN group_in_group.father_id IS 'Automatic member';


--
-- Name: log; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE log (
    id serial NOT NULL PRIMARY KEY,
    dt timestamp without time zone NOT NULL,
    contact_id integer NOT NULL REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    action integer NOT NULL,
    target text NOT NULL,
    target_repr text NOT NULL,
    property text,
    property_repr text,
    change text
);


--
-- PostgreSQL database dump complete
--
