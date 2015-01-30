#!/usr/bin/make -f
all:
	cd core && ../manage compilemessages
	cd extensions/externalmessages && ../../manage compilemessages
	mkdir -p /usr/lib/ngw/static
	./manage collectstatic --verbosity 1 --noinput
	./manage upgradedb --verbosity 2
	py3compile core extensions
clean:
	rm -rf static/
	rm -f mailing/generated/*
	py3clean core extensions

README.html: README.rst
	rst2html README.rst README.html
