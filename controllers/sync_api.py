"""
Controller package for main Sync API
"""
import sys, os
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in ( 'lib', 'extlib' ) ])

import logging, simplejson, struct
from datetime import datetime
from time import mktime
from google.appengine.api import users
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from fxsync.utils import profile_auth, json_request, json_response
from fxsync.models import Profile, Collection, WBO

WEAVE_ERROR_INVALID_PROTOCOL = 1
WEAVE_ERROR_INCORRECT_CAPTCHA = 2
WEAVE_ERROR_INVALID_USERNAME = 3
WEAVE_ERROR_NO_OVERWRITE = 4
WEAVE_ERROR_USERID_PATH_MISMATCH = 5
WEAVE_ERROR_JSON_PARSE = 6
WEAVE_ERROR_MISSING_PASSWORD = 7
WEAVE_ERROR_INVALID_WBO = 8
WEAVE_ERROR_BAD_PASSWORD_STRENGTH = 9
WEAVE_ERROR_INVALID_RESET_CODE = 10
WEAVE_ERROR_FUNCTION_NOT_SUPPORTED = 11
WEAVE_ERROR_NO_EMAIL = 12
WEAVE_ERROR_INVALID_COLLECTION = 13

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
        return wbo.to_dict()

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
        self.request.body_json.update({
            'user_name': user_name, 
            'collection_name': collection_name,
            'wbo_id': wbo_id
        })
        (wbo, errors) = WBO.insert_or_update(self.request.body_json)
        if not wbo:
            self.response.set_status(400, message="Bad Request")
            self.response.out.write(WEAVE_ERROR_INVALID_WBO)
            return None
        else:
            return wbo.modified

class StorageCollectionHandler(SyncApiBaseRequestHandler):

    @profile_auth
    def get(self, user_name, collection_name):
        """Filtered retrieval of WBOs from a collection"""
        collection = Collection.get_by_profile_and_name(
            self.request.profile, collection_name
        )

        params = dict((k,self.request.get(k, None)) for k in (
            'id', 'ids', 'predecessorid', 'parentid', 
            'older', 'newer',
            'index_above', 'index_below', 
            'full', 'limit', 'offset', 'sort'
        ))

        params['full'] = params['full'] is not None

        if params['ids']: params['ids'] = params['ids'].split(',')

        for n in ('index_above', 'index_below', 'limit', 'offset'):
            if params[n]: params[n] = int(params[n])

        for n in ('older', 'newer'):
            if params[n]: params[n] = float(params[n])

        # TODO: Need a generator here? 
        # TODO: Find out how not to load everything into memory.

        out = collection.retrieve(**params)

        accept = ('Accept' not in self.request.headers 
            and 'application/json' or self.request.headers['Accept'])

        if 'application/newlines' == accept:
            self.response.headers['Content-Type'] = 'application/newlines'
            for x in out:
                self.response.out.write("%s\n" % simplejson.dumps(x))

            #elif 'application/whoisi' == accept:
            #    self.response.headers['Content-Type'] = 'application/whoisi'
            #    for x in out:
            #        if params['full']:
            #            self.response.out.write('%s%s' % (
            #                struct.pack('!I', x['id']), 
            #                simplejson.dumps(x)
            #            ))
            #        else:
            #            self.response.out.write('%s%s' % (
            #                struct.pack('!I', x), 
            #                simplejson.dumps(x)
            #            ))

        else:
            self.response.headers['Content-Type'] = 'application/json'
            rv = [x for x in out]
            self.response.out.write(simplejson.dumps(rv))

    @profile_auth
    @json_request
    @json_response
    def post(self, user_name, collection_name):
        """Bulk update of WBOs in a collection"""
        out = { 'modified': None, 'success': [], 'failed': {} }

        collection = Collection.get_by_profile_and_name(
            self.request.profile, collection_name
        )

        self.log = logging.getLogger()
        for wbo_data in self.request.body_json:
            if 'id' not in wbo_data: continue
            self.log.debug("WBO %s" % simplejson.dumps(wbo_data))
            wbo_data['collection'] = collection
            wbo_id = wbo_data['id']
            (wbo, errors) = WBO.insert_or_update(wbo_data)
            out['modified'] = wbo.modified
            if wbo:
                out['success'].append(wbo_id)
            else:
                out['failed'][wbo_id] = errors

        return out

    @profile_auth
    @json_response
    def delete(self, user_name, collection_name):
        """Bulk deletion of WBOs from a collection"""
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
