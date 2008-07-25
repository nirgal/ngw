# -*- encoding: utf-8 -*-

from ngw.gp.alchemy_models import *

class TransactionMiddleware(object):
    def process_request(self, request):
        # todo: transaction.begin
        return None

    def process_exception(self, request, exception):
        print "Session.rollback"
        Session.rollback()
        print "Session.clear"
        Session.clear() # removed pending saves
        return None

    def process_response(self, request, response):
        try:
            print "Session.commit"
            Session.commit() # This does a flush too
            print "Session.clear"
            Session.clear()
        except:
            print "Session.rollback"
            Session.rollback()
            print "Session.clear"
            Session.clear()
            raise
        return response
