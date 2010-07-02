"""
Controller package for main Sync API
"""
import sys, os
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in ( 'lib', 'extlib' ) ])

import logging
from datetime import datetime
from time import mktime
from google.appengine.api import users
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from fxsync.utils import profile_auth, json_request, json_response
from fxsync.models import Profile, Collection, WBO

def main():
    """Main entry point for controller"""
    util.run_wsgi_app(application())

def application():
    """Build the WSGI app for this package"""
    return webapp.WSGIApplication([
        (r'/sync/1.0/(.*)/info/collections', CollectionsHandler),
        (r'/sync/1.0/(.*)/info/collection_counts', CollectionCountsHandler),
        (r'/sync/1.0/(.*)/info/quota', QuotaHandler),
        (r'/sync/1.0/(.*)/storage/(.*)/(.*)', StorageItemHandler),
        (r'/sync/1.0/(.*)/storage/(.*)', StorageCollectionHandler),
        (r'/sync/1.0/(.*)/storage/', StorageHandler),
    ], debug=True)

class SyncApiBaseRequestHandler(webapp.RequestHandler):
    """Base class for all sync API request handlers"""
    def initialize(self, req, resp):
        webapp.RequestHandler.initialize(self, req, resp)
        self.log = logging.getLogger()

class CollectionsHandler(SyncApiBaseRequestHandler):
    """Handler for collection list"""
    @profile_auth
    @json_response
    def get(self, user_name):
        """List user's collections and last modified times"""
        return Collection.get_timestamps(self.request.profile)

class CollectionCountsHandler(SyncApiBaseRequestHandler):
    """Handler for collection counts"""
    @profile_auth
    @json_response
    def get(self, user_name):
        """Get counts for a user's collections"""
        return Collection.get_counts(self.request.profile)

class QuotaHandler(SyncApiBaseRequestHandler):
    """Handler for quota checking"""
    @profile_auth
    @json_response
    def get(self, user_name):
        """Get the quotas for a user's profile"""
        # TODO: Need to actually implement space / quota counting.
        return [ 0, 9999 ]

class StorageItemHandler(SyncApiBaseRequestHandler):
    """Handler for individual collection items"""

    @profile_auth
    @json_response
    def get(self, user_name, collection_name, wbo_id):
        """Get an item from the collection"""
        collection = Collection.get_by_profile_and_name(
            self.request.profile, collection_name
        )
        wbo = WBO.get_by_collection_and_wbo_id(collection, wbo_id)
        if not wbo: return self.error(404)
        wbo_data = dict( (k,getattr(wbo, k)) for k in ( 
            'sortindex', 'parentid', 'predecessorid', 
            'payload', 'payload_size', 'modified'
        ) if getattr(wbo, k))
        wbo_data['id'] = wbo_id
        return wbo_data

    @profile_auth
    def delete(self, user_name, collection_name, wbo_id):
        """Delete an item from the collection"""
        collection = Collection.get_by_profile_and_name(
            self.request.profile, collection_name
        )
        wbo = WBO.get_by_collection_and_wbo_id(collection, wbo_id)
        if not wbo: return self.error(404)
        wbo.delete()
        self.response.out.write('%s' % WBO.get_time_now())

    @profile_auth
    @json_request
    @json_response
    def put(self, user_name, collection_name, wbo_id):
        """Insert or update an item in the collection"""
        collection = Collection.get_by_profile_and_name(
            self.request.profile, collection_name
        )

        wbo_now = WBO.get_time_now()
        body = self.request.body_json

        wbo_data = dict((k,f(body[k])) for k,f in (
            ('sortindex', int), 
            ('parentid', str),
            ('predecessorid', str), 
            ('payload', str),
        ) if (k in body))
        
        wbo_data.update({
            'profile': self.request.profile,
            'collection': collection,
            'modified': wbo_now,
            'wbo_id': wbo_id,
            'payload_size': len(wbo_data['payload']),
        })

        wbo = WBO.get_by_collection_and_wbo_id(collection, wbo_id)
        if not wbo:
            wbo_data['key_name'] = WBO.build_key_name(collection, wbo_id)
            wbo_data['parent'] = collection.key()
            wbo = WBO(**wbo_data)
        else:
            for k,v in wbo_data.items(): setattr(wbo, k, v)
        wbo.put()

        return wbo.modified

class StorageCollectionHandler(SyncApiBaseRequestHandler):

    @profile_auth
    def get(self, user_name, collection_name):
        params = dict((k,self.request.get(k, False)) for k in (
            'ids', 'predecessorid', 'parentid', 
            'older', 'newer',
            'index_above', 'index_below', 
            'full', 'limit', 'offset', 'sort'
        ))
        self.response.out.write('StorageCollectionHandler %s' % user_name)

    @profile_auth
    def post(self, user_name, collection_name):
        # BULK UPDATE: https://wiki.mozilla.org/Labs/Weave/Sync/1.0/API#POST
        self.response.out.write('StorageCollectionHandler %s' % user_name)

    @profile_auth
    @json_response
    def delete(self, user_name, collection_name):
        # TODO: Accept params for get() to selectively delete.
        collection = Collection.get_by_profile_and_name(
            self.request.profile, collection_name
        )
        collection.delete()
        return WBO.get_time_now()

class StorageHandler(SyncApiBaseRequestHandler):

    @profile_auth
    def delete(self, user_name):
        # DELETE EVERYTHING!
        self.response.out.write('StorageHandler %s' % user_name)

if __name__ == '__main__': main()
