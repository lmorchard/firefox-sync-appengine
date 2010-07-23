"""
Model classes for fxsync
"""
import sys, os
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in ( 'lib', 'extlib' ) ])

import datetime, random, string, hashlib, logging
from google.appengine.ext import db
from google.appengine.api import users
from django.utils import simplejson

from datetime import datetime
from time import mktime

WBO_PAGE_SIZE = 25

def paginate(items, page_len):
    """Paginage a list of items into a list of page lists"""
    total_len = len(items)
    num_pages = total_len / page_len
    (d, m)    = divmod(total_len, page_len)
    if m > 0: 
        num_pages += 1
    return (
        items[ (i * page_len):(i * page_len + page_len) ] 
        for i in xrange(num_pages)
    )

class Profile(db.Model):
    """Sync profile associated with logged in account"""
    user        = db.UserProperty(auto_current_user_add=True)
    user_name   = db.StringProperty(required=True)
    user_id     = db.StringProperty(required=True)
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

    def delete(self):
        c_keys = []
        cs = Collection.all().ancestor(self)
        for c in cs:
            c_keys.append(c.key())
            while True:
                # HACK: This smells like trouble - switch to Task Queue?
                w_keys = WBO.all(keys_only=True).ancestor(c).fetch(500)
                if not w_keys: break
                db.delete(w_keys)
        db.delete(c_keys)
        db.Model.delete(self)
    
class Collection(db.Model):
    profile = db.ReferenceProperty(Profile, required=True)
    name    = db.StringProperty(required=True)

    builtin_names = (
        'clients', 'crypto', 'forms', 'history', 'keys', 'meta', 
        'bookmarks', 'prefs','tabs','passwords'
    )

    def delete(self):
        while True:
            # HACK: This smells like trouble - switch to Task Queue?
            w_keys = WBO.all(keys_only=True).ancestor(self).fetch(500)
            if not w_keys: break
            db.delete(w_keys)
        db.Model.delete(self)

    def retrieve(self, 
            full=None, wbo=None, count=None, direct_output=None, 
            id=None, ids=None, 
            parentid=None, predecessorid=None, 
            newer=None, older=None, 
            index_above=None, index_below=None,
            sort=None, limit=None, offset=None):

        limit  = (limit is not None) and limit or 1000 #False
        offset = (offset is not None) and offset or 0 #False
        sort   = (sort is not None) and sort or 'index'

        if id:
            w = WBO.all().ancestor(self).filter('wbo_id =', id).get()
            if count: return 1
            if wbo: return [ w ]
            if full: return [ w.to_dict() ]
            return [ w.wbo_id ]

        elif ids:
            if count: return len(ids)
            wbos = []
            id_pages = paginate(ids, WBO_PAGE_SIZE)
            for id_page in id_pages:
                q = WBO.all().ancestor(self).filter('wbo_id IN', id_page)
                wbos.extend(q.fetch(WBO_PAGE_SIZE))
            if wbo: return wbos
            if full: return ( w.to_dict() for w in wbos )
            return ( w.wbo_id for w in wbos )

        final_query = None
        queries = []

        # TODO: Work out how to use keys_only=True here again.

        if parentid is not None:
            queries.append(WBO.all().ancestor(self)
                .filter('parentid =', parentid))
            
        if predecessorid is not None:
            queries.append(WBO.all().ancestor(self)
                .filter('predecessorid =', predecessorid))

        if index_above is not None or index_below is not None:
            q = WBO.all().ancestor(self)
            if index_above: q.filter('sortindex >', index_above)
            if index_below: q.filter('sortindex <', index_below)
            q.order('sortindex')
            queries.append(q)

        if newer is not None or older is not None:
            q = WBO.all().ancestor(self)
            if newer: q.filter('modified >', newer)
            if older: q.filter('modified <', older)
            q.order('modified')
            queries.append(q)

        if len(queries) == 0:
            final_query = WBO.all().ancestor(self)
        elif len(queries) == 1:
            final_query = queries[0]
        else:
            key_set = None
            for q in queries:
                # HACK: I don't think setting _keys_only is kosher
                q._keys_only = True
                keys = set(str(x) for x in q.fetch(limit, offset))
                if key_set is None:
                    key_set = keys
                else:
                    key_set = key_set & keys
            
            keys = [db.Key(x) for x in key_set]
            key_pages = paginate(keys, WBO_PAGE_SIZE)

            # Use the key pages for a combo result here.

            final_query = WBO.all().ancestor(self).filter('__key__ IN', keys)

        # Determine which sort order to use.
        if 'oldest' == sort: order = 'modified'
        elif 'newest' == sort: order = '-modified'
        else: order = '-sortindex'
        final_query.order(order)

        # Return IDs / full objects as appropriate for full option.
        if count:
            return final_query.count()
        if wbo:
            return ( w for w in final_query.fetch(limit, offset) )
        if not full:
            return ( w.wbo_id for w in final_query.fetch(limit, offset) )
        else:
            return ( w.to_dict() for w in final_query.fetch(limit, offset) )

    @classmethod
    def build_key_name(cls, name):
        return name

    @classmethod
    def get_by_profile_and_name(cls, profile, name):
        """Get a collection by name and user"""
        return Collection.get_or_insert(
            parent=profile,
            key_name=cls.build_key_name(name),
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

    # TODO: Move this to config somewhere
    WEAVE_PAYLOAD_MAX_SIZE = 262144 

    def to_dict(self):
        """Produce a dict representation, usable for JSON response"""
        wbo_data = dict( (k,getattr(self, k)) for k in ( 
            'sortindex', 'parentid', 'predecessorid', 
            'payload', 'payload_size', 'modified'
        ) if getattr(self, k))
        wbo_data['id'] = self.wbo_id
        return wbo_data

    @classmethod
    def build_key_name(cls, wbo_data):
        """Build a collection-unique key name for a WBO"""
        return wbo_data['wbo_id']

    @classmethod
    def from_json(cls, data_in):
        wbo, errors = None, []

        if 'collection' not in data_in:
            if 'user_name' in data_in:
                data_in['profile'] = Profile.get_by_user_name(data_in['user_name'])
                del data_in['user_name']

            if 'collection_name' in data_in:
                data_in['collection'] = Collection.get_by_profile_and_name(
                    data_in['profile'], data_in['collection_name']
                )
                del data_in['profile']
                del data_in['collection_name']

        if 'id' in data_in:
            data_in['wbo_id'] = data_in['id']
            del data_in['id']

        wbo_data = dict((k,data_in[k]) for k in (
            'sortindex',
            'parentid',
            'predecessorid',
            'payload',
        ) if (k in data_in))
        
        wbo_now    = WBO.get_time_now()
        wbo_id     = data_in['wbo_id']
        collection = data_in['collection']

        wbo_data.update({
            'collection': collection,
            'parent': collection,
            'modified': wbo_now,
            'wbo_id': wbo_id,
        })

        if 'payload' in wbo_data:
            wbo_data['payload_size'] = len(wbo_data['payload'])

        errors = cls.validate(wbo_data)
        if len(errors) > 0: return (None, errors)

        wbo_data['key_name'] = cls.build_key_name(wbo_data)
        wbo = WBO(**wbo_data)

        return (wbo, errors)

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
        return WBO.all().ancestor(collection).filter('wbo_id =', wbo_id).get()

    @classmethod
    def exists_by_collection_and_wbo_id(cls, collection, wbo_id):
        """Get a WBO by wbo_id"""
        return WBO.all().ancestor(collection).filter('wbo_id =', wbo_id).count() > 0

    @classmethod
    def validate(cls, wbo_data):
        """Validate the contents of this WBO"""
        errors = []

        if 'id' in wbo_data:
            wbo_data['wbo_id'] = wbo_data['id']
            del wbo_data['id']

        if ('wbo_id' not in wbo_data or not wbo_data['wbo_id'] or 
                len(wbo_data['wbo_id']) > 64 or '/' in wbo_data['wbo_id']):
            errors.append('invalid id')

        if ('collection' not in wbo_data or not wbo_data['collection'] or 
                len(wbo_data['collection'].name)>64):
            errors.append('invalid collection')

        if ('parentid' in wbo_data):
            if (len(wbo_data['parentid']) > 64):
                errors.append('invalid parentid')
            elif 'collection' in wbo_data:
                if not cls.exists_by_collection_and_wbo_id(wbo_data['collection'], wbo_data['parentid']):
                    errors.append('invalid parentid')

        if ('predecessorid' in wbo_data):
            if (len(wbo_data['predecessorid']) > 64):
                errors.append('invalid predecessorid')
            elif 'collection' in wbo_data:
                if not cls.exists_by_collection_and_wbo_id(wbo_data['collection'], wbo_data['predecessorid']):
                    errors.append('invalid predecessorid')

        if 'modified' not in wbo_data or not wbo_data['modified']:
            errors.append('no modification date')
        else:
            if type(wbo_data['modified']) is not float:
                errors.append('invalid modified date')

        if 'sortindex' in wbo_data:
            if (type(wbo_data['sortindex']) is not int or 
                    wbo_data['sortindex'] > 999999999 or
                    wbo_data['sortindex'] < -999999999):
                errors.append('invalid sortindex')

        if 'payload' in wbo_data:
            if (cls.WEAVE_PAYLOAD_MAX_SIZE and 
                    len(wbo_data['payload']) > cls.WEAVE_PAYLOAD_MAX_SIZE):
                errors.append('payload too large')
            else:
                try:
                    data = simplejson.loads(wbo_data['payload'])
                except ValueError, e:
                    errors.append('payload needs to be json-encoded')

        return errors
