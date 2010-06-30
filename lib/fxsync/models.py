"""
Model classes for fxsync
"""
import datetime, random, string
from google.appengine.ext import db
from google.appengine.api import users

class Profile(db.Model):
    user_id     = db.StringProperty(required=True)
    user_name   = db.StringProperty(required=True)
    password    = db.StringProperty(required=True)
    created_at  = db.DateTimeProperty(auto_now_add=True)
    updated_at  = db.DateTimeProperty(auto_now=True)

    @classmethod
    def find_user_and_profile(cls):
        """Try finding a sync profile associated with the current user"""
        user = users.get_current_user()
        profile = db.GqlQuery(
            "SELECT * FROM Profile WHERE user_id = :1", 
            user.user_id()
        ).get()
        return user, profile

    @classmethod
    def find_by_user_name(cls, user_name):
        return cls.all().filter('user_name =', user_name).get()        

    @classmethod
    def generate_password(cls):
        """Generate a random alphanumeric password"""
        return ''.join(random.sample(string.letters+string.digits, 16))

    @classmethod
    def authenticate(cls, user_name, password):
        profile = cls.find_by_user_name(user_name)
        if profile and profile.password == password:
            return True
        else:
            return False
    
class Collection(db.Model):
    user_id         = db.StringProperty(required=True)
    collection_name = db.StringProperty(required=True)

class WBO(db.Model):
    wbo_id          = db.StringProperty(required=True)
    user_id         = db.StringProperty(required=True)
    collection_name = db.StringProperty(required=True)
    parent_id       = db.StringProperty(required=True)
    predecessor_id  = db.StringProperty(required=True)
    sortindex       = db.IntegerProperty(default=0)
    modified        = db.IntegerProperty(default=0)
    payload         = db.TextProperty(required=True)
    payload_size    = db.IntegerProperty(default=0)
