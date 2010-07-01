import sys, os, os.path
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in (
    'lib', 'extlib', 'controllers'
)])

import unittest, logging, datetime, time, base64
import webtest, json, random, string
from google.appengine.ext import webapp, db

from fxsync.models import Profile, Collection, WBO
import sync_api

class SyncApiTests(unittest.TestCase):
    """Unit tests for the Sync API controller"""

    USER_NAME = 'tester123'
    USER_ID   = '86753095551212'
    PASSWD    = 'QsEdRgTh12345'

    def setUp(self):
        """Prepare for unit test"""
        self.log = logging.getLogger()
        self.log.setLevel(logging.DEBUG)
        
        # There shouldn't already be a profile, but just in case...
        profile = Profile.get_by_user_name(self.USER_NAME)
        if profile: profile.delete()

        # Create a new profile for tests.
        self.profile = Profile(
            user_id   = self.USER_ID,
            user_name = self.USER_NAME,
            password  = self.PASSWD
        )
        self.profile.put()
        
        # Build the app test harness.
        self.app = webtest.TestApp(sync_api.application())

    def tearDown(self):
        """Clean up after unit test"""
        # Is this actually needed, since storage is mocked?
        self.profile.delete()
        q = WBO.all()
        for o in q: o.delete()
        q = Collection.all()
        for o in q: o.delete()

    def test_profile_auth(self):
        """Ensure access to sync API requires profile auth"""
        resp = self.app.get(
            '/sync/1.0/%s/info/collections' % self.USER_NAME,
            status=401
        )
        self.assertEqual('401 Authorization Required', resp.status)
        resp = self.app.get(
            '/sync/1.0/%s/info/collections' % self.USER_NAME,
            headers=self.build_auth_header()
        )
        self.assertEqual('200 OK', resp.status)

    def test_storage_single_put_get_delete(self):
        """Exercise storing and getting a single object"""
        collection = 'foo'
        wbo_data = { "id": 1, "sortindex": 1, "payload": "1234567890asdfghjkl" }
        auth_header = self.build_auth_header()
        storage_url = '/sync/1.0/%s/storage/%s/%s' % ( 
            self.USER_NAME, collection, wbo_data['id'] 
        )

        resp = self.app.get(storage_url, headers=auth_header, status=404)

        resp = self.app.put(storage_url, headers=auth_header, status=400,
            params="THIS IS NOT JSON")
        self.assertEqual('400 Bad Request', resp.status)

        resp = self.app.put(storage_url, headers=auth_header, 
            params=json.dumps(wbo_data))
        self.assertEqual('200 OK', resp.status)
        self.assert_(WBO.get_time_now() >= float(resp.body))

        resp = self.app.get(storage_url, headers=auth_header)
        resp_wbo_data = json.loads(resp.body)
        self.assertEqual(wbo_data['payload'], resp_wbo_data['payload'])

        resp = self.app.delete(storage_url, headers=auth_header)
        self.assertEqual('200 OK', resp.status)
        self.assert_(WBO.get_time_now() >= float(resp.body))

        resp = self.app.get(storage_url, headers=auth_header, status=404)

    def test_collection_operations(self):
        """Exercise collection counts and timestamps"""
        expected_counts = {
            'clients':2, 'crypto':0, 'forms':6, 'history':0, 'keys':10,
            'meta':12, 'bookmarks':14, 'prefs':16, 'tabs':18, 'passwords':20,
            'foo':12, 'bar':14, 'baz':16
        }
        expected_dates = { }
        expected_count = 0

        auth_header = self.build_auth_header()

        # Insert objects with random contents to satisfy the expected counts
        for collection_name, count in expected_counts.items():
            base_url = '/sync/1.0/%s/storage/%s' % (
                self.USER_NAME, collection_name
            )
            for i in range(count):
                # Build up a random content object for insertion.
                wbo_id = random.randint(0, 1000000)
                wbo_json = json.dumps({
                    'sortindex': random.randint(0, 1000),
                    'payload': ''.join(random.sample(string.letters, 16))
                })
                url = '%s/%s' % (base_url, wbo_id)
                resp = self.app.put(url, headers=auth_header, params=wbo_json)

                # Record the reported timestamp and increment overall count.
                expected_dates[collection_name] = float(resp.body)
                expected_count += 1

        # Ensure the counts match expected
        resp = self.app.get(
            '/sync/1.0/%s/info/collection_counts' % (self.USER_NAME),
            headers=auth_header
        )
        resp_data = json.loads(resp.body)
        self.assertEqual(expected_counts, resp_data)

        # Ensure all timestamps are same or newer than expected.
        resp = self.app.get(
            '/sync/1.0/%s/info/collections' % (self.USER_NAME),
            headers=auth_header
        )
        resp_data = json.loads(resp.body)
        for k,v in expected_dates.items():
            self.assert_(k in resp_data)
            self.assert_(resp_data[k] >= expected_dates[k])

        # Verify the count of all objects after creating
        result_count = WBO.all().count()
        self.assertEqual(expected_count, result_count)

        # Delete each collection and verify the count after
        curr_count = expected_count
        for collection_name in expected_counts.keys():
            url = '/sync/1.0/%s/storage/%s' % (self.USER_NAME, collection_name)
            resp = self.app.delete(url, headers=auth_header)
            self.assert_(WBO.get_time_now() >= float(resp.body))

            expected_count -= expected_counts[collection_name]
            result_count = WBO.all().count()
            self.assertEqual(expected_count, result_count)

        # No WBOs should be left after all collections deleted.
        result_count = WBO.all().count()
        self.assertEqual(0, result_count)

    def build_auth_header(self, user_name=None, passwd=None):
        user_name = user_name or self.USER_NAME
        passwd = passwd or self.PASSWD
        return {
            'Authorization': 'Basic %s' % base64.b64encode(
                '%s:%s' % (self.USER_NAME, self.PASSWD)
            )
        }

