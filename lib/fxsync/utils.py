"""
Random utilities

TODO: Put these in a better named package, instead of this grab bag
"""
import sys, os, os.path
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in ('lib', 'extlib')])

import urllib, base64, simplejson
from fxsync.models import Profile

def json_request(func):
    """Decorator to auto-decode JSON request body"""
    def cb(wh, *args, **kwargs):
        try:
            wh.request.body_json = simplejson.loads(wh.request.body)
        except ValueError:
            wh.response.set_status(400, message="Bad Request")
            wh.response.out.write("Invalid JSON request body")
        else:
            return func(wh, *args, **kwargs)
    return cb

def json_response(func):
    """Decorator to auto-encode return value as JSON response"""
    def cb(wh, *args, **kwargs):
        rv = func(wh, *args, **kwargs)
        if rv is not None:
            wh.response.headers['Content-Type'] = 'application/json'
            wh.response.out.write(simplejson.dumps(rv))
            return rv
    return cb

def profile_auth(func):
    """Decorator to wrap controller methods in profile auth requirement"""
    def cb(wh, *args, **kwargs):
        url_user = urllib.unquote(args[0])

        auth_header = wh.request.headers.get('Authorization')
        if auth_header == None:
            wh.response.set_status(401, message="Authorization Required")
            wh.response.headers['WWW-Authenticate'] = 'Basic realm="firefox-sync"'
            return
        
        auth_parts = auth_header.split(' ')
        user_arg, pass_arg = base64.b64decode(auth_parts[1]).split(':')

        valid_authen = (
            (url_user == user_arg) 
                and 
            Profile.authenticate(user_arg, pass_arg)
        )

        if not valid_authen:
            wh.response.set_status(401, message="Authorization Required")
            wh.response.headers['WWW-Authenticate'] = 'Basic realm="firefox-sync"'
            wh.response.out.write("Unauthorized")
        else:
            wh.request.profile = Profile.get_by_user_name(user_arg)
            return func(wh, *args, **kwargs)

    return cb
