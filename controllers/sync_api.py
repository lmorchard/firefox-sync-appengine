"""
"""
import sys, os
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in 
    ( 'lib', 'extlib' ) 
])

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

def main():
    application = webapp.WSGIApplication(
        [
            (r'/sync/1.0/(.*)/info/collections', CollectionsHandler), # GET
            (r'/sync/1.0/(.*)/info/collection_counts', CollectionCountsHandler), # GET
            (r'/sync/1.0/(.*)/info/quota', QuotaHandler), # GET
            (r'/sync/1.0/(.*)/storage/(.*)/(.*)', StorageItemHandler), # GET, PUT, DELETE
            (r'/sync/1.0/(.*)/storage/(.*)', StorageCollectionHandler), # GET, POST, DELETE
            (r'/sync/1.0/(.*)/storage/', StorageHandler), # DELETE
        ], 
        debug=True
    )
    util.run_wsgi_app(application)

class CollectionsHandler(webapp.RequestHandler):
    def get(self, user_name):
        self.response.out.write('CollectionsHandler %s' % user_name)

class CollectionCountsHandler(webapp.RequestHandler):
    def get(self, user_name):
        self.response.out.write('CollectionCountsHandler %s' % user_name)

class QuotaHandler(webapp.RequestHandler):
    def get(self, user_name):
        self.response.out.write('QuotaHandler %s' % user_name)

class StorageItemHandler(webapp.RequestHandler):
    def get(self, user_name, collection, item_id):
        self.response.out.write('StorageItemHandler %s' % user_name)
    def put(self, user_name, collection, item_id):
        self.response.out.write('StorageItemHandler %s' % user_name)
    def delete(self, user_name, collection, item_id):
        self.response.out.write('StorageItemHandler %s' % user_name)

class StorageCollectionHandler(webapp.RequestHandler):
    def get(self, user_name, collection):
        self.response.out.write('StorageCollectionHandler %s' % user_name)
    def post(self, user_name, collection):
        self.response.out.write('StorageCollectionHandler %s' % user_name)
    def delete(self, user_name, collection):
        self.response.out.write('StorageCollectionHandler %s' % user_name)

class StorageHandler(webapp.RequestHandler):
    def delete(self, user_name):
        self.response.out.write('StorageHandler %s' % user_name)

if __name__ == '__main__':
    main()
