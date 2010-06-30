"""
Random utilities
"""
import urllib, base64
from fxsync.models import *

def profileauth(func):
    """Decorator to wrap controller methods in profile authen"""

    def auth(wh, *args, **kwargs):

        # User name from URL always comes as first arg.
        url_user = urllib.unquote(args[0])

        auth_header = wh.request.headers.get('Authorization')
        if auth_header == None:
            wh.response.set_status(401, message="Authorization Required")
            wh.response.headers['WWW-Authenticate'] = 'Basic realm="firefox-sync"'
        
        else:
            auth_parts = auth_header.split(' ')
            user_arg, pass_arg = base64.b64decode(auth_parts[1]).split(':')

            valid_authen = \
                (url_user == user_arg) and \
                Profile.authenticate(user_arg, pass_arg)

            if not valid_authen:
                wh.response.set_status(401, message="Authorization Required")
                wh.response.headers['WWW-Authenticate'] = 'Basic realm="firefox-sync"'
                wh.response.out.write("Unauthorized")
            else:
                return func(wh, *args, **kwargs)

    return auth
