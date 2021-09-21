#!/usr/bin/make -f
all:
	cd core && ../manage.py compilemessages
	cd extensions/externalmessages && ../../manage.py compilemessages
	cd extensions/matrix && ../../manage.py compilemessages
	mkdir -p /usr/lib/ngw/static
	./manage.py collectstatic --verbosity 1 --noinput
	./manage.py migrate --verbosity 1
	py3compile core extensions
clean:
	rm -rf static/
	rm -f mailing/generated/*
	py3clean core extensions

README.html: README.rst
	rst2html README.rst README.html

isort:
	isort --check-only --diff --dont-skip __init__.py `find -name '*py' | grep -v ./core/wsgi.py`

flake8:
	flake8 --exclude=.svn,CVS,.bzr,.hg,.git,__pycache__,.tox,.eggs,*.egg,wsgi.py .

makemessages:
	cd core && ../manage.py makemessages --locale fr -v 2 && ../manage.py makemessages --locale fr -v 2 -d djangojs --extension js,mjs
	cd extensions/externalmessages && ../../manage.py makemessages --locale fr -v 2
	cd extensions/matrix && ../../manage.py makemessages --locale fr -v 2
