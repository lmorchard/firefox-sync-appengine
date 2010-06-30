#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import sys, os, os.path
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in 
    ( 'lib', 'extlib', 'models' ) 
])

import random, string
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util, template
from fxsync.models import *

def main():
    application = webapp.WSGIApplication(
        [
            ('/start', StartHandler),
        ], 
        debug=True
    )
    util.run_wsgi_app(application)

class StartHandler(webapp.RequestHandler):

    def get(self):
        user, profile = self.find_profile_for_user()
        return self.render_template('main/start.html', {
            'user': user, 
            'profile': profile,
            'sync_url': '%s/sync/1.0' % self.request.application_url
        })

    def post(self):
        user, profile = self.find_profile_for_user()
        action = self.request.get('action', False)

        if not profile and 'create_profile' == action:
            # Create a new profile, with auto-generated password
            new_profile = Profile(
                user_id   = user.user_id(),
                user_name = user.nickname(),
                password  = self.generate_password()
            )
            new_profile.put()

        elif profile and 'regenerate_password' == action:
            # Generate and set a new password for the profile
            profile.password = self.generate_password()
            profile.put()

        elif profile and 'delete_profile' == action:
            # Delete the profile
            profile.delete()

        return self.redirect('/start')

    def find_profile_for_user(self):
        """Try finding a sync profile associated with the current user"""
        user = users.get_current_user()
        profile = db.GqlQuery(
            "SELECT * FROM Profile WHERE user_id = :1", 
            user.user_id()
        ).get()
        return user, profile

    def render_template(self, path, data=None):
        """Shortcut for rendering templates"""
        if (data is None): data = {}
        self.response.out.write(template.render(
            '%s/templates/%s' % (base_dir, path), data
        ))

    def generate_password(self):
        return ''.join(random.sample(string.letters+string.digits, 16))

if __name__ == '__main__':
    main()
