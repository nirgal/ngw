#!/usr/bin/make -f
all:
	cd /usr/lib/ngw/core/ && /usr/lib/ngw/manage compilemessages
	cd /usr/lib/ngw/extensions/externalmessages/ && /usr/lib/ngw/manage compilemessages
	mkdir -p /usr/lib/ngw/static
	./manage collectstatic --verbosity 1 --noinput
	./manage upgradedb --verbosity 2
