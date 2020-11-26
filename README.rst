.. This document uses rst format. See http://docutils.sourceforge.net/
   Quick start: http://docutils.sourceforge.net/docs/user/rst/quickref.html
   Use "make README.html" to make the nice HTML version (requires python3-docutils or python-docutils)
   vim: ts=4 et

===
NGW
===

Introduction
============

NGW is a kind of groupware. It supports customizable contacts, groups, events, news, files, and messages.

It provide a high level of permission settings including which group can see/change which contact fields, which other groups.

It can also pilot permission to a jabber installation as extensions.

This is the installation guide, intended for system administrators.


Debian repository setup (optional)
==================================

It is recommanded to use Debian 10 (Buster) or above. All sources are available, so you can use other settings if you want to, but you are on your own then.

Here's a suggested /etc/apt/sources.list::

    deb     http://http.debian.net/debian/       buster           main
    deb-src http://http.debian.net/debian/       buster           main
    deb     http://security.debian.org/          buster/updates   main
    deb-src http://security.debian.org/          buster/updates   main

If you want the packages from nirgal.com, have a look at the README file at https://nirgal.com/debian/


Requirements
============

Standard packages::

    aptitude install python3-django python3-psycopg2 postgresql libapache2-mod-wsgi-py3 gettext python3-socks python3-cracklib python3-magic python3-pil tor make python3-gnupg libjs-jquery-ui openssl python3-django-session-security isort flake8

If you set up nirgal.com repository as described above, just run::

    aptitude install libjs-xgcalendar python3-decoratedstr

The sources of the other packages are available at nirgal.com/debian.


Use the source
==============

If you did not yet, you need to clone the git repository::

    git clone https://github.com/nirgal/ngw.git

As root, make a symbolic link from the git copy to ``/usr/lib``. Base directory must be ``/usr/lib/ngw``.

That way, you can have upgrades with a simple ``git pull``. You need to run the ``Makefile`` after each upgrades (not yet on the first installation). So it is suggested you create a ``.git/hooks/post-merge`` 755 file::

    #!/bin/bash
    echo "Running $0" >&2
    make

The source is flake8 compliant. See http://flake8.readthedocs.org/

Please ensure you are committing correct code by invoking ``make flake8`` before any commit. You'll need to install ``flake8`` package.
Then it is recommended you create a ``.git/hooks/pre-commit`` 755 file to do that automatically::

    #!/bin/sh
    make isort flake8


Postgres setup
==============

Ngw depends on some advanced PostgreSQL functions, such as recursive queries. So this is a requirement. You cannot use another database.

Create a user ngw (or something else)::

    postgres@localhost:~$ createuser ngw --no-superuser --createdb --no-createrole

Set a password for it::

    postgres@localhost:~$ psql -c "\password ngw"

Create a database ``ngw`` with owner ngw::

    postgres@localhost:~$ createdb ngw -E unicode -O ngw


Application setup
=================

You need to create and tune your ``settings.py``. It is recommended to use ``settings.py.exemple`` as a template. Then:

- Put your database user/password there
- Put something in ``SECRET_KEY``::

    from django.utils.crypto import get_random_string
    get_random_string(50, 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)')

- Run the initialisation / update script:

    There are many things that needs to be done to have a running system:

    - Create the database structure, populate the initial data, and create the extra views and functions.
    - Compile the translations.
    - Collect the static files in a single place.

    You just need to run::

    $ make

- Create an administrative account on the application level. Use::

    $ ./manage.py createsuperuser

- Now the application should run locally::

    $ ./manage.py runserver


Apache
======

User or group ``www-data`` should have write access to ``/usr/lib/ngw/media/fields``, ``/usr/lib/ngw/media/g`` and ``/usr/lib/ngw/media/messages``. If you want to run the debug ``runserver`` command from time to time, I suggest you ``chown :www-data`` that folder, with ``g+ws`` mode.

Make sure ``/etc/mime.types`` serves ``.mjs`` files as ``application/javascript``. This is the default in Debian 11+ (bullseye).


Cron
====

You should to set up a cron tab::

    */5 * * * * /usr/lib/ngw/manage.py msgsync -v 2
    0 * * * * /usr/lib/ngw/manage.py clearsessions

You may also want to setup some kind of backup here.


Optionnal extensions
====================

ejabberd synchronisation
------------------------

You can have one group automatically grant access to a local ejabberd.

See ``extentions/xmpp/README``

gnupg support
-------------

Public keys can be */usr/lib/ngw/.gnupg*::

    mkdir /var/lib/ngw
    chown www-data /var/lib/ngw

Right now, keys needs to be imported by hand: ``gpg --homedir /var/lib/ngw/ --import akey.key``

Add ``Listen 11371`` at the end of the ``/etc/apache2/ports.conf`` to have an ``hkp://`` compatible server (Download only)

Uncomment gpg keyring directory in ``settings.py`` (``GPG_HOME``)

License
=======

Unless otherwise specified, the project is licensed using a BSD-2 license. See LICENSE for the full text.

Files in core/static/ngw/twemoji are from the Twitter emoji project at https://github.com/twitter/twemoji
(C) Twitter using a BSD-2 license.

Files in core/static/ngw/notoemoji are from the Noto Emoji at https://github.com/googlefonts/noto-emoji
They use an Apache License 2.0.
