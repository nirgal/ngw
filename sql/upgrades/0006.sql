UPDATE contact_group_news SET title=left(title, 64);
ALTER TABLE contact_group_news ALTER COLUMN title TYPE varchar(64);
