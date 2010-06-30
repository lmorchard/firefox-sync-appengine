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
            ('/sync/user/1.0/(.*)', UserHandler), # GET, PUT, DELETE
            ('/sync/user/1.0/(.*)/email', EmailHandler), # POST
            ('/sync/user/1.0/(.*)/password', PasswordHandler), # POST
            ('/sync/user/1.0/(.*)/node/weave', NodeHandler), # GET (unauth)
            ('/sync/user/1.0/(.*)/password_reset', PasswordResetHandler), # GET
        ], 
        debug=True
    )
    util.run_wsgi_app(application)

class UserApiHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write("USER API!")
    def put(self):
        self.response.out.write("USER API!")
    def delete(self):
        self.response.out.write("USER API!")

class EmailHandler(webapp.RequestHandler):
    def post(self):
        self.response.out.write("USER API!")

class PasswordHandler(webapp.RequestHandler):
    def post(self):
        self.response.out.write("USER API!")

class NodeHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write("USER API!")

class PasswordResetHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write("USER API!")

if __name__ == '__main__':
    main()

