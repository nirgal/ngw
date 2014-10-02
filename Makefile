#!/usr/bin/make -f
all:
	cd core && ../manage compilemessages
	cd extensions/externalmessages && ../../manage compilemessages
	mkdir -p /usr/lib/ngw/static
	./manage collectstatic --verbosity 1 --noinput
	./manage upgradedb --verbosity 2
clean:
	rm -rf static/
	rm -f mailing/generated/*
