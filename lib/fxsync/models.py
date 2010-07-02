"""
Model classes for fxsync
"""
import datetime, random, string, hashlib, logging
from google.appengine.ext import db
from google.appengine.api import users

from datetime import datetime
from time import mktime

class Profile(db.Model):
    """Sync profile associated with logged in account"""
    user_name   = db.StringProperty(required=True)
    password    = db.StringProperty(required=True)
    created_at  = db.DateTimeProperty(auto_now_add=True)
    updated_at  = db.DateTimeProperty(auto_now=True)

    @classmethod
    def get_user_and_profile(cls):
        """Try finding a sync profile associated with the current user"""
        user = users.get_current_user()
        profile = Profile.all().filter('user_id =', user.user_id()).get()
        return user, profile

    @classmethod
    def get_by_user_name(cls, user_name):
        """Get a profile by user name"""
        return cls.all().filter('user_name =', user_name).get()        

    @classmethod
    def generate_password(cls):
        """Generate a random alphanumeric password"""
        return ''.join(random.sample(string.letters+string.digits, 16))

    @classmethod
    def authenticate(cls, user_name, password):
        """Attempt to authenticate the given user name and password"""
        profile = cls.get_by_user_name(user_name)
        return ( profile and profile.password == password )
    
class Collection(db.Model):
    profile = db.ReferenceProperty(Profile, required=True)
    name    = db.StringProperty(required=True)

    builtin_names = (
        'clients', 'crypto', 'forms', 'history', 'keys', 'meta', 
        'bookmarks', 'prefs','tabs','passwords'
    )

    def delete(self):
        q = WBO.get_by_collection(self)
        for w in q: w.delete()
        db.Model.delete(self)

    @classmethod
    def build_key_name(cls, profile, name):
        return 'collection:%s:%s' % (profile.key(), name)

    @classmethod
    def get_by_profile_and_name(cls, profile, name):
        """Get a collection by name and user"""
        return Collection.get_or_insert(
            parent=profile,
            key_name=cls.build_key_name(profile, name),
            profile=profile,
            name=name
        )

    @classmethod
    def is_builtin(cls, name):
        """Determine whether a named collection is built-in"""
        return name in cls.builtin_names

    @classmethod
    def get_timestamps(cls, profile):
        """Assemble last modified for user's built-in and ad-hoc collections"""
        c_list = dict((n, 0) for n in cls.builtin_names)
        q = Collection.all().ancestor(profile)
        for c in q:
            w = WBO.all().ancestor(c).order('-modified').get()
            c_list[c.name] = w and w.modified or 0
        return c_list 

    @classmethod
    def get_counts(cls, profile):
        """Assemble counts for user's built-in and ad-hoc collections"""
        c_list = dict((n, 0) for n in cls.builtin_names)
        q = Collection.all().ancestor(profile)
        for c in q:
            c_list[c.name] = WBO.all().ancestor(c).count()
        return c_list 

class WBO(db.Model):
    collection      = db.ReferenceProperty(Collection, required=True)
    wbo_id          = db.StringProperty(required=True)
    modified        = db.FloatProperty(required=True)
    parentid        = db.StringProperty()
    predecessorid   = db.StringProperty()
    sortindex       = db.IntegerProperty(default=0)
    payload         = db.TextProperty(required=True)
    payload_size    = db.IntegerProperty(default=0)

    @classmethod
    def build_key_name(cls, collection, wbo_id):
        return 'wbo-%s-%s-%s' % (
            collection.profile.user_name, collection.name, wbo_id
        )

    @classmethod
    def get_time_now(cls):
        """Get the current time in microseconds"""
        tn = datetime.now()
        tt = tn.timetuple()
        tm = mktime(tt)
        ms = (tn.microsecond/1000000.0)
        st = tm+ms
        return round(st,2)

    @classmethod
    def get_by_collection(cls, collection):
        return cls.all().ancestor(collection)

    @classmethod
    def get_by_collection_and_wbo_id(cls, collection, wbo_id):
        """Get a WBO by wbo_id"""
        return cls.get_by_key_name(
            cls.build_key_name(collection, wbo_id),
            parent=collection
        )
