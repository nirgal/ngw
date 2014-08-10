#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import division, absolute_import, print_function, unicode_literals

import os
import logging
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import NoArgsCommand
from django.conf import settings
from django.db import connection
from core.models import Config


def get_version():
    '''
    Returns current database structure version, or 1 if not found.
    '''
    try:
        version = Config.objects.get(id='db version').text
    except Config.DoesNotExist:
        return 1
    try:
        return int(version)
    except ValueError:
        return 1


def set_version(version):
    '''
    Store database structure version
    '''
    version_obj, created = Config.objects.get_or_create(id='db version')
    version_obj.text = str(version)
    version_obj.save()


class Command(NoArgsCommand):
    help = 'Update database structure'

    def handle_noargs(self, **options):
        logger = logging.getLogger('upgradedb')
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(name)s %(levelname)-8s: %(message)s'))
        logger.addHandler(handler)
        verbosity = int(options['verbosity'])
        if verbosity == 0:
            logger.setLevel(logging.ERROR)
        elif verbosity == 1:
            logger.setLevel(logging.WARNING)
        elif verbosity == 2:
            logger.setLevel(logging.INFO)
        elif verbosity == 3:
            logger.setLevel(logging.DEBUG)
        logger.propagate = False

        try:
            base_dir = settings.BASE_DIR
        except AttributeError as e:
            # raise ImproperlyConfigured(('You need to add an "BASE_DIR" in your settings.py: "%s"'
            #     % e))
            raise ImproperlyConfigured('You need to add an "BASE_DIR" in your settings.py')
        
        cursor = connection.cursor()

        while(True):
            version = get_version()
            logger.debug('Current version is %s', version)
            
            upgrade_sql_file = 'sql/upgrades/%04d.sql' % (version + 1)
            upgrade_sql_file = os.path.join(base_dir, upgrade_sql_file)
            logger.debug('Looking for %s', upgrade_sql_file)
            try:
                sql = open(upgrade_sql_file, 'r').read()
            except IOError: # FileNotFoundError is better, but is python3 only
                logger.info('Database structure is up to date. version=%s.', version)
                return

            logger.info('Executing sql from %s:\n%s', upgrade_sql_file, sql)
            cursor.execute(sql)

            version += 1
            set_version(version)
            logger.warning('Database structure upgraded to version %s', version)
