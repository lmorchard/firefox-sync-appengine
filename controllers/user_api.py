"""
Controller package for Sync User API, profile management
"""
import sys, os
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in ( 'lib', 'extlib' ) ])

import urllib
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from fxsync.models import *
from fxsync.utils import profileauth

def main():
    """Main entry point for controller"""
    application = webapp.WSGIApplication(
        [
            (r'/sync/user/1.0/(.*)/node/weave', NodeHandler), # GET (unauth)
            (r'/sync/user/1.0/(.*)/email', EmailHandler), # POST
            (r'/sync/user/1.0/(.*)/password', PasswordHandler), # POST
            (r'/sync/user/1.0/(.*)/password_reset', PasswordResetHandler), # GET
            (r'/sync/user/1.0/(.*)/?', UserHandler), # GET (unauth), PUT, DELETE
        ], 
        debug=True
    )
    util.run_wsgi_app(application)

class NodeHandler(webapp.RequestHandler):
    """Sync cluster node location"""
    
    def get(self, user_name):
        """Return full URL to the sync cluster node (ie. the sync API)"""
        self.response.out.write('%s/sync' % self.request.application_url)

class UserHandler(webapp.RequestHandler):
    """User URL handler"""

    def get(self, user_name):
        """Determine whether the user exists"""
        user_name = urllib.unquote(user_name)
        profile = Profile.find_by_user_name(user_name)
        return self.response.out.write(profile and '1' or '0')

    def put(self, user_name):
        """Profile sign up"""
        # This server disallows sign-up
        self.response.set_status(403)

    @profileauth
    def delete(self, user_name):
        """Allow profile deletion"""
        user_name = urllib.unquote(user_name)
        profile = Profile.find_by_user_name(user_name)
        profile.delete()
        return self.response.out.write('success')

class EmailHandler(webapp.RequestHandler):

    @profileauth
    def post(self, user_name):
        """Profile email modification"""
        # This server disallows email change
        self.response.set_status(403)

class PasswordHandler(webapp.RequestHandler):
    
    @profileauth
    def post(self, user_name):
        """Profile password modification"""
        # This server disallows password change (for now)
        self.response.set_status(403)

class PasswordResetHandler(webapp.RequestHandler):
   
    @profileauth
    def get(self, user_name):
        """Profile password reset trigger"""
        # This server disallows password reset
        self.response.set_status(403)

if __name__ == '__main__': main()
