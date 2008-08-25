# -*- encoding: utf-8 -*-

from ngw.gp.alchemy_models import *

PRINT_TRANSACTION_ENDS=False

class TransactionMiddleware(object):
    def process_request(self, request):
        # todo: transaction.begin
        return None

    def process_exception(self, request, exception):
        if PRINT_TRANSACTION_ENDS:
            print "Session.rollback"
        Session.rollback()
        if PRINT_TRANSACTION_ENDS:
            print "Session.clear"
        Session.clear() # removed pending saves
        return None

    def process_response(self, request, response):
        try:
            if PRINT_TRANSACTION_ENDS:
                print "Session.commit"
            Session.commit() # This does a flush too
            if PRINT_TRANSACTION_ENDS:
                print "Session.clear"
            Session.clear()
        except:
            if PRINT_TRANSACTION_ENDS:
                print "Session.rollback"
            Session.rollback()
            if PRINT_TRANSACTION_ENDS:
                print "Session.clear"
            Session.clear()
            raise
        return response
