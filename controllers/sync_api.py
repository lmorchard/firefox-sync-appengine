"""
Controller package for main Sync API
"""
import sys, os
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in ( 'lib', 'extlib' ) ])

import json, logging
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
    return webapp.WSGIApplication(
        [
            (r'/sync/1.0/(.*)/info/collections', CollectionsHandler),
            (r'/sync/1.0/(.*)/info/collection_counts', CollectionCountsHandler),
            (r'/sync/1.0/(.*)/info/quota', QuotaHandler),
            (r'/sync/1.0/(.*)/storage/(.*)/(.*)', StorageItemHandler),
            (r'/sync/1.0/(.*)/storage/(.*)', StorageCollectionHandler),
            (r'/sync/1.0/(.*)/storage/', StorageHandler),
        ], 
        debug=True
    )

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
        return Collection.get_timestamps(self.request.profile.user_id)

class CollectionCountsHandler(SyncApiBaseRequestHandler):
    """Handler for collection counts"""
    @profile_auth
    @json_response
    def get(self, user_name):
        """Get counts for a user's collections"""
        return Collection.get_counts(self.request.profile.user_id)

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
        wbo = WBO.get_by_collection_and_id(collection_name, wbo_id)
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
        wbo = WBO.get_by_collection_and_id(collection_name, wbo_id)
        if not wbo: return self.error(404)
        wbo.delete()
        self.response.out.write('%s' % WBO.get_time_now())

    @profile_auth
    @json_request
    def put(self, user_name, collection_name, wbo_id):
        """Insert or update an item in the collection"""
        wbo_now = WBO.get_time_now()
        body = self.request.body_json

        wbo_data = dict((k,f(body[k])) for k,f in (
            ('sortindex', int), ('parentid', str),
            ('predecessorid', str), ('payload', str),
        ) if (k in body))
        
        wbo_data.update({
            'modified': wbo_now,
            'wbo_id': wbo_id,
            'user_id': self.request.profile.user_id,
            'collection_name': collection_name,
            'payload_size': len(wbo_data['payload']),
        })

        wbo = WBO.get_by_collection_and_id(collection_name, wbo_id)
        if not wbo:
            wbo = WBO(**wbo_data)
        else:
            for k,v in wbo_data.items(): setattr(wbo, k, v)
        wbo.put()

        self.response.out.write('%s' % wbo.modified)

class StorageCollectionHandler(SyncApiBaseRequestHandler):

    @profile_auth
    def get(self, user_name, collection):
        self.response.out.write('StorageCollectionHandler %s' % user_name)

    @profile_auth
    def post(self, user_name, collection):
        self.response.out.write('StorageCollectionHandler %s' % user_name)

    @profile_auth
    @json_response
    def delete(self, user_name, collection_name):
        Collection.delete_by_collection_name_and_user_id(
            collection_name, self.request.profile.user_id
        )
        return WBO.get_time_now()

class StorageHandler(SyncApiBaseRequestHandler):

    @profile_auth
    def delete(self, user_name):
        self.response.out.write('StorageHandler %s' % user_name)

if __name__ == '__main__': main()
