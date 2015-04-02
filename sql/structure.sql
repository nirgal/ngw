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
    end_date date,
    budget_code character varying(10) DEFAULT ''::character varying NOT NULL,
    system boolean DEFAULT false NOT NULL,
    mailman_address character varying(255),
    sticky boolean DEFAULT false NOT NULL
);


--
-- Name: choice_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE choice_group (
    id serial NOT NULL PRIMARY KEY,
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

CREATE INDEX choice_choice_group_id_index ON choice (choice_group_id);


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
    contact_id integer NOT NULL REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    contact_field_id integer NOT NULL REFERENCES contact_field(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    value text,
    PRIMARY KEY (contact_id, contact_field_id)
) WITH OIDS;

CREATE INDEX contact_field_value_contact_id_index ON contact_field_value (contact_id);
CREATE INDEX contact_field_value_contact_field_id_index ON contact_field_value (contact_field_id);


--
-- Name: contact_in_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_in_group (
    id serial NOT NULL PRIMARY KEY,
    contact_id integer NOT NULL REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    group_id integer NOT NULL REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    flags integer NOT NULL,
    note text
);

CREATE INDEX contact_in_group_contact_id_index ON contact_in_group (contact_id);
CREATE INDEX contact_in_group_group_id_index ON contact_in_group (group_id);

--
-- Name: contact_group_news; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_group_news (
    id serial NOT NULL PRIMARY KEY,
    author_id integer REFERENCES contact(id) ON UPDATE CASCADE ON DELETE CASCADE,
    contact_group_id integer REFERENCES contact_group(id) ON UPDATE CASCADE ON DELETE CASCADE,
    date timestamp with time zone NOT NULL,
    title varchar(64) NOT NULL,
    text text NOT NULL
);


--
-- Name: group_in_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE group_in_group (
    father_id integer NOT NULL REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    subgroup_id integer NOT NULL REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    PRIMARY KEY (father_id, subgroup_id)
) WITH OIDS;

CREATE INDEX group_in_group_contact_id_index ON group_in_group (father_id);
CREATE INDEX group_in_group_group_id_index ON group_in_group (subgroup_id);

--
-- Name: group_manage_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE group_manage_group (
    father_id integer NOT NULL REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    subgroup_id integer NOT NULL REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    flags integer NOT NULL,
    PRIMARY KEY (father_id, subgroup_id)
) WITH OIDS;

CREATE INDEX group_manage_group_contact_id_index ON group_manage_group (father_id);
CREATE INDEX group_manage_group_group_id_index ON group_manage_group (subgroup_id);

--
-- Name: log; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE log (
    id serial NOT NULL PRIMARY KEY,
    dt timestamp with time zone NOT NULL,
    contact_id integer NOT NULL REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    action integer NOT NULL,
    target text NOT NULL,
    target_repr text NOT NULL,
    property text,
    property_repr text,
    change text
);

--
-- Name: contact_message; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE contact_message (
    id serial NOT NULL PRIMARY KEY,
    contact_id integer NOT NULL REFERENCES contact(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    group_id integer NOT NULL REFERENCES contact_group(id) MATCH FULL ON UPDATE CASCADE ON DELETE CASCADE,
    send_date timestamp with time zone NOT NULL,
    read_date timestamp with time zone,
    read_by_id integer REFERENCES contact(id) MATCH SIMPLE ON UPDATE CASCADE ON DELETE SET NULL,
    is_answer boolean DEFAULT false NOT NULL,
    subject varchar(64) NOT NULL DEFAULT 'no title',
    text text,
    sync_info text
);
-- TODO: postgresql 9.2 supports json type for syncinfo

ALTER TABLE contact_field ADD CONSTRAINT contact_field_has_choice1 CHECK (
        (type<>'choice' AND type<>'MULTIPLECHOICE' AND type<>'DOUBLECHOICE')
        OR choice_group_id IS NOT NULL
);
ALTER TABLE contact_field ADD CONSTRAINT contact_field_has_choice2 CHECK (
        type<>'DOUBLECHOICE'
        OR choice_group2_id IS NOT NULL
);
--
-- PostgreSQL database dump complete
--
