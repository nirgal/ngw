# -*- encoding: utf-8 -*-

from ngw.core.alchemy_models import *

PRINT_TRANSACTION_ENDS=True

class TransactionMiddleware(object):
    def process_request(self, request):
        # todo: transaction.begin
        return None

    def process_exception(self, request, exception):
        if PRINT_TRANSACTION_ENDS:
            print "Session.rollback"
        Session.rollback()
        if PRINT_TRANSACTION_ENDS:
            print "Session.expunge_all"
        Session.expunge_all() # removed pending saves
        return None

    def process_response(self, request, response):
        try:
            if PRINT_TRANSACTION_ENDS:
                print "Session.commit"
            Session.commit() # This does a flush too
            if PRINT_TRANSACTION_ENDS:
                print "Session.expunge_all"
            Session.expunge_all()
        except:
            if PRINT_TRANSACTION_ENDS:
                print "Session.rollback"
            Session.rollback()
            if PRINT_TRANSACTION_ENDS:
                print "Session.expunge_all"
            Session.expunge_all()
            raise
        return response
