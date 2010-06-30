"""
Model classes for fxsync
"""
import datetime
from google.appengine.ext import db
from google.appengine.api import users

class Profile(db.Model):
    user_id     = db.StringProperty(required=True)
    user_name   = db.StringProperty(required=True)
    password    = db.StringProperty(required=True)
    created_at  = db.DateTimeProperty(auto_now_add=True)
    updated_at  = db.DateTimeProperty(auto_now=True)
    
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
