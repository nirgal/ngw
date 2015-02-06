.. This document uses rst format. See http://docutils.sourceforge.net/
   Quick start: http://docutils.sourceforge.net/docs/user/rst/quickref.html
   Use "make README.html" to make the nice HTML version (requires python3-docutils or python-docutils)

===
NGW
===

Introduction
============

NGW is a kind of groupware. It supports customizable contacts, groups, events, news, files, and messages.

It provide a high level of permission settings including which group can see/change which contact fields, which other groups.

It can alos pilot permission to jabber and phpbb installation as exentions.

This is the installation guide, intended for system administrators.


Debian repository setup (optional)
==================================
It is recommanded to use Debian 7 (Wheezy) or above. All the source is available, so you can use other settings if you want, but you are on your own, then.

Here's a suggested /etc/apt/sources.list::

    deb     http://http.debian.net/debian/       wheezy           main contrib non-free
    deb-src http://http.debian.net/debian/       wheezy           main contrib non-free
    deb     http://security.debian.org/          wheezy/updates   main contrib non-free
    deb-src http://security.debian.org/          wheezy/updates   main contrib non-free
    deb     http://ftp.debian.org/debian         wheezy-backports main contrib non-free
    deb-src http://ftp.debian.org/debian         wheezy-backports main contrib non-free

Make sure you defined wich default Debian version you want, so that backports are not installed automatically::

    echo 'APT::Default-Release "stable";' > /etc/apt/apt.conf.d/10_defaultrelease

If you want the packages from nirgal.com, have a look at the README file at http://nirgal.com/debian/


Requirements
============

Standard packages::

    aptitude install python3-django python3-psycopg2 postgresql libapache2-mod-wsgi-py3 gettext python3-uno python3-cracklib tor make python3-gnupg libjs-jquery-ui

You need python-django version 1.7, available in Debian stable-backports at::

    apt-get -t wheezy-backports install python3-django

If you set up nirgal.com repository as described above, just run::

    aptitude install libjs-xgcalendar python3-django-session-security python3-decoratedstr oomailing python3-socksipy

If you did not, *python3-socksipy* and *python3-django-session-security* are now officially in debian experimental. The sources of the other packages are available at nirgal.com/debian.


Use the source
==============

If you did not yet, you need to clone the git repository::

    git clone https://github.com/nirgal/ngw.git

As root, make a symbolic link from the git copy to /usr/lib. Base directory must be */usr/lib/ngw*.

That way, you can have upgrades with a simple *git pull*. You need to run the *Makefile* after each upgrades (not yet on the first installation). So it is suggested you create a *.git/hooks/post-merge* file 755 file::

    #!/bin/bash
    echo "Running $0" >&2
    make


Postgres setup
==============

Ngw depends on some advanced postgres functions, such as recursive querries. So this is a requirement.

Create a user ngw (or something else)::

    postgres@localhost:~$ createuser ngw --no-superuser --createdb --no-createrole

Set a password for it::

    postgres@localhost:~$ psql -c "\password ngw"

Create a database ngw with owner ngw::

    postgres@localhost:~$ createdb ngw -E unicode -O ngw

Create the structure, populate the initial data, and create the extra views and functions::

    $ psql -h localhost -U ngw ngw -f sql/structure.sql
    $ psql -h localhost -U ngw ngw -f sql/initialdata.sql
    $ psql -h localhost -U ngw ngw -f sql/functions.sql
    $ ./manage syncdb


Application setup
=================

You need to create and tune your  *settings.py*. It is recommended to use *settings.py.exemple* as a template. Then:

- Put your database user/password there
- Put something in SECRET_KEY::

    from django.utils.crypto import get_random_string
    get_random_string(50, 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)')

You now need to create an admin account on the application level. Use::

    ./manage createsuperuser

Now the application should run locally::

    make
    ./manage runserver


Apache
======

Enable ssl in apache::

    a2enmod ssl

Generate self-signed certificate::

    openssl req -nodes -x509 -days 3650 -new -newkey rsa:2048 -subj /CN=ngw.example.net -keyout ngw.key -out ngw.crt

Listen on port 443
    Add a new line "Listen 443" to /etc/apache2/ports.conf" if it's now there allready

Enable virtual hosts on https:
    Add a new line::

	 NameVirtualHost *:443

    before::

         Listen 443

User or group www-data should have write access to /usr/lib/ngw/media/g and /usr/lib/ngw/media/messages. If you want to run the debug runserver command from time to time, I suggest you chown :www-data that folder, with g+ws mode.

The web server also needs to have write permission to where the pdf are generated::

    chown www-data: /usr/lib/ngw/mailing/generated/


Cron
====

You should to set up a cron tab::

    */5 * * * * /usr/lib/ngw/manage msgsync -v 2
    0 * * * * /usr/lib/ngw/manage clearsessions

You may also want to setup some kind of backup here.


Optionnal extensions
====================

phpbb3 synchronisation
----------------------

You can use ngw groups to manage phpbb3 permissions, so that some contacts will
automatically have access to some forums.
See extentions/phpbb3/README

ejabberd synchronisation
------------------------

You can have one group automatically grant access to a local ejabberd.
See extentions/xmpp/README

gnupg support
-------------

Public keys can be */usr/lib/ngw/.gnupg*::

    mkdir /var/lib/ngw
    chown www-data /var/lib/ngw

Right now, keys needs to be imported by hand: gpg --homedir /var/lib/ngw/ --import akey.key

Add *Listen 11371* at the end of the */etc/apache2/ports.conf* to have an hkp:// compatible server (Download only)

Uncomment gpg keyring directory in settings.py (GPG_HOME)