"""
Model classes for fxsync
"""
import datetime, random, string
from google.appengine.ext import db
from google.appengine.api import users

from datetime import datetime
from time import mktime

class Profile(db.Model):
    """Sync profile associated with logged in account"""
    user_id     = db.StringProperty(required=True)
    user_name   = db.StringProperty(required=True)
    password    = db.StringProperty(required=True)
    created_at  = db.DateTimeProperty(auto_now_add=True)
    updated_at  = db.DateTimeProperty(auto_now=True)

    @classmethod
    def get_user_and_profile(cls):
        """Try finding a sync profile associated with the current user"""
        user = users.get_current_user()
        profile = db.GqlQuery(
            "SELECT * FROM Profile WHERE user_id = :1", 
            user.user_id()
        ).get()
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
        if profile and profile.password == password:
            return True
        else:
            return False
    
class Collection(db.Model):
    user_id         = db.StringProperty(required=True)
    collection_name = db.StringProperty(required=True)

    builtin_names = (
        'clients', 'crypto', 'forms', 'history', 'keys', 'meta', 
        'bookmarks', 'prefs','tabs','passwords'
    )

    @classmethod
    def get_by_collection_name_and_user_id(cls, collection_name, user_id):
        """Get a collection by name and user"""
        return (
            cls.all()
            .filter('collection_name =', collection_name)
            .filter('user_id =', user_id)
            .get()        
        )

    @classmethod
    def delete_by_collection_name_and_user_id(cls, collection_name, user_id):
        q = (
            WBO.all()
            .filter('collection_name =', collection_name)
            .filter('user_id =', user_id)
        )
        for w in q: w.delete()
        c = cls.get_by_collection_name_and_user_id(collection_name, user_id)
        if c: c.delete()

    @classmethod
    def is_builtin(cls, collection_name):
        """Determine whether a named collection is built-in"""
        return collection_name in cls.builtin_names

    @classmethod
    def get_timestamps(cls, user_id):
        """Assemble last modified for user's built-in and ad-hoc collections"""
        c_list = {}

        for name in cls.builtin_names:
            w = (
                WBO.all()
                .filter('collection_name =', name)
                .filter('user_id =', user_id)
                .order('-modified')
                .get()
            )
            c_list[name] = w and w.modified or 0

        q = Collection.all().filter('user_id =', user_id)
        for c in q:
            w = (
                WBO.all()
                .filter('collection_name =', c.collection_name)
                .filter('user_id =', user_id)
                .order('-modified')
                .get()
            )
            c_list[c.collection_name] = w and w.modified or 0

        return c_list 

    @classmethod
    def get_counts(cls, user_id):
        """Assemble counts for user's built-in and ad-hoc collections"""
        counts = {}

        for name in cls.builtin_names:
            counts[name] = (
                WBO.all()
                .filter('collection_name =', name)
                .filter('user_id =', user_id)
                .count()
            )

        q = Collection.all().filter('user_id =', user_id)
        for c in q:
            counts[c.collection_name] = (
                WBO.all()
                .filter('collection_name =', c.collection_name)
                .filter('user_id =', user_id)
                .count()
            )

        return counts 

class WBO(db.Model):
    wbo_id          = db.StringProperty(required=True)
    user_id         = db.StringProperty(required=True)
    collection_name = db.StringProperty(required=True)
    modified        = db.FloatProperty(required=True)
    parentid        = db.StringProperty()
    predecessorid   = db.StringProperty()
    sortindex       = db.IntegerProperty(default=0)
    payload         = db.TextProperty(required=True)
    payload_size    = db.IntegerProperty(default=0)

    def put(self):
        db.Model.put(self)
        # Ensure Collection entities exist for ad-hoc collections.
        # TODO: Use memcache to optimize here.
        if not Collection.is_builtin(self.collection_name):
            c = Collection.get_by_collection_name_and_user_id(
                self.collection_name, self.user_id
            )
            if not c:
                c = Collection(
                    user_id = self.user_id,
                    collection_name = self.collection_name
                )
                c.put()

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
    def get_by_collection_and_id(cls, collection_name, wbo_id):
        """Get a WBO by wbo_id"""
        return (
            cls.all()
            .filter('wbo_id =', wbo_id)
            .filter('collection_name =', collection_name)
            .order('-modified')
            .get() 
        )
