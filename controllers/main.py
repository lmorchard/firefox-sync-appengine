"""
Controller package for basic web UI.
"""
import sys, os, os.path
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in ('lib', 'extlib') ])

import random, string
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util, template
from fxsync.models import Profile, Collection, WBO

def main():
    """Main entry point for controller"""
    application = webapp.WSGIApplication(
        [
            ('/start', StartHandler),
        ], 
        debug=True
    )
    util.run_wsgi_app(application)

class StartHandler(webapp.RequestHandler):
    """Sync start page handler"""

    def get(self):
        """Display the sync start page"""
        user, profile = Profile.get_user_and_profile()
        return self.render_template('main/start.html', {
            'user': user, 
            'profile': profile,
            'sync_url': '%s/sync' % self.request.application_url
        })

    def post(self):
        """Process a POST'd command from the sync start page.

        HACK: This is a little hacky, pivoting on a form field command, but oh well.
        """
        user, profile = Profile.get_user_and_profile()
        action = self.request.get('action', False)

        if not profile and 'create_profile' == action:
            # Create a new profile, with auto-generated password
            new_profile = Profile(
                user_id   = user.user_id(),
                user_name = user.nickname(),
                password  = Profile.generate_password()
            )
            new_profile.put()

        elif profile and 'regenerate_password' == action:
            # Generate and set a new password for the profile
            profile.password = Profile.generate_password()
            profile.put()

        elif profile and 'delete_profile' == action:
            # Delete the profile
            profile.delete()

        return self.redirect('/start')

    def render_template(self, path, data=None):
        """Shortcut for rendering templates"""
        if (data is None): data = {}
        self.response.out.write(template.render(
            '%s/templates/%s' % (base_dir, path), data
        ))

if __name__ == '__main__': main()
