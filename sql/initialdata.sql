--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = off;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET escape_string_warning = off;

SET search_path = public, pg_catalog;

--
-- Data for Name: choice_group; Type: TABLE DATA; Schema: public; Owner: ngw
--

COPY choice_group (id, name, sort_by_key) FROM stdin;
1	Pays	f
9	Oui / Non	t
41	Status du mot de passe	t
\.

SELECT pg_catalog.setval('choice_group_id_seq', 46, true);

--
-- Data for Name: choice; Type: TABLE DATA; Schema: public; Owner: ngw
--

COPY choice (choice_group_id, key, value) FROM stdin;
1	fr	France
1	uk	Royaume Uni
1	ch	Suisse
1	it	Italie
9	1	Oui
9	2	Non
41	1	Generated
41	3	User defined
41	2	Generated and mailed
\.


--
-- Data for Name: config; Type: TABLE DATA; Schema: public; Owner: ngw
--

COPY config (id, text) FROM stdin;
groups header	
columns	name,field_7,field_8,field_10,field_52
banner	<big>NGW</big> Group Ware
phpbb acl dictionary	
query_page_length	100
\.


--
-- Data for Name: contact; Type: TABLE DATA; Schema: public; Owner: ngw
--

COPY contact (id, name) FROM stdin;
1	Default admin
\.

SELECT pg_catalog.setval('contact_id_seq', 1080, true);

--
-- Data for Name: contact_group; Type: TABLE DATA; Schema: public; Owner: ngw
--

COPY contact_group (id, name, description, field_group, date, budget_code, system, mailman_address, has_news, sticky) FROM stdin;
1	Contacts	Ensemble des contacts	t	\N		t		f	f
2	Utilisateurs	Ensemble des personnes qui ont un identifiant et un mot de passe.\r\nVoir aussi "Utilisateurs NGW" et "Utilisateurs Forum".	t	\N		t	\N	f	f
8	Admins	Ils peuvent ajouter des contacts dans n'importe quel groupe, et tout voir.	f	\N		t		f	f
9	Observateurs	Ils peuvent tout voir, mais n'ont pas accès en écriture sur les groupes.	f	\N		t		f	f
52	Utilisateurs NGW	Les personnes de ce groupe peuvent se connecter à la base de données.	f	\N		t	\N	f	f
53	Utilisateurs Forum	Les personnes de ce groupe peuvent se connecter au forum (non disponible).	t	\N		t	\N	f	f
\.

SELECT pg_catalog.setval('contact_group_id_seq', 100, true);

--
-- Data for Name: contact_field; Type: TABLE DATA; Schema: public; Owner: ngw
--

COPY contact_field (id, name, hint, type, contact_group_id, sort_weight, choice_group_id, system, "default") FROM stdin;
1	Login	Nom avec lequel vous vous connectez au système	TEXT	2	390	\N	t	\N
2	Mot de passe	Ne pas modifier. Utiliser le bouton "Change password" après avoir cliqué sur votre nom en haut à droite.	PASSWORD	2	400	\N	t	\N
3	Dernière connexion	Ce champ est mis à jour automatiquement	DATETIME	2	440	\N	t	\N
4	Colonnes	Ce champ est mis à jour automatiquement	TEXT	2	450	\N	t	\N
5	Filtres personnels	Ce champ est mis à jour automatiquement	TEXT	2	460	\N	t	\N
7	Courriel		EMAIL	1	10	\N	f	\N
8	GSM		PHONE	1	50	\N	f	\N
9	Rue		LONGTEXT	1	110	\N	t	\N
10	Tél.fixe		PHONE	1	30	\N	f	\N
11	code postal		TEXT	1	120	\N	t	\N
14	Ville		TEXT	1	130	\N	t	\N
48	Pays		CHOICE	1	140	1	t	fr
73	phpbb user id	Identifiant du forum. Ne pas toucher.	NUMBER	53	430	\N	t	\N
74	Mot de passe nouveau		PASSWORD	2	410	\N	t	\N
75	Status du mot de passe	Mis à jour automatiquement	CHOICE	2	420	41	t	\N
\.

SELECT pg_catalog.setval('contact_field_id_seq', 100, true);

--
-- Data for Name: contact_field_value; Type: TABLE DATA; Schema: public; Owner: ngw
--

COPY contact_field_value (contact_id, contact_field_id, value) FROM stdin;
1	1	admin
1	2	/BHLc/u80sjCs
1	3	2013-10-23 10:19:15
1	4	name,field_7,field_92,field_100
1	7	test@exemple.net
1	11	75000
1	14	Paris
1	48	fr
1	75	3
\.


--
-- Data for Name: contact_in_group; Type: TABLE DATA; Schema: public; Owner: ngw
--

COPY contact_in_group (contact_id, group_id, flags, note) FROM stdin;
1	8	9	\N
\.


--
-- Data for Name: group_in_group; Type: TABLE DATA; Schema: public; Owner: ngw
--

COPY group_in_group (father_id, subgroup_id) FROM stdin;
1	2
2	53
2	52
52	8
52	9
\.
