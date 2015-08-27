#!/usr/bin/make -f
all:
	cd core && ../manage.py compilemessages
	cd extensions/externalmessages && ../../manage.py compilemessages
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
	isort -c --diff --dont-skip __init__.py -b fcntl -b ssl -p ngw -o gnupg `find -name '*py' | grep -v ./core/wsgi.py`

flake8:
	flake8 .
