#!/usr/bin/make -f
all:
	cd core && ../manage.py compilemessages
	cd extensions/externalmessages && ../../manage.py compilemessages
	mkdir -p /usr/lib/ngw/static
	./manage.py collectstatic --verbosity 1 --noinput
	./manage.py upgradedb --verbosity 2
	py3compile core extensions
clean:
	rm -rf static/
	rm -f mailing/generated/*
	py3clean core extensions

README.html: README.rst
	rst2html README.rst README.html
