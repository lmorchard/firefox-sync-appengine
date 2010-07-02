import sys, os, os.path
base_dir = os.path.dirname( os.path.dirname(__file__) )
sys.path.extend([ os.path.join(base_dir, d) for d in (
    'lib', 'extlib', 'controllers'
)])

import unittest, logging, datetime, time, base64
import webtest, simplejson, random, string
from google.appengine.ext import webapp, db

from fxsync.models import Profile, Collection, WBO
import sync_api

class SyncApiTests(unittest.TestCase):
    """Unit tests for the Sync API controller"""

    USER_NAME = 'tester123'
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
            params=simplejson.dumps(wbo_data))
        self.assertEqual('200 OK', resp.status)
        self.assert_(WBO.get_time_now() >= float(resp.body))

        resp = self.app.get(storage_url, headers=auth_header)
        resp_wbo_data = simplejson.loads(resp.body)
        self.assertEqual(wbo_data['payload'], resp_wbo_data['payload'])

        resp = self.app.delete(storage_url, headers=auth_header)
        self.assertEqual('200 OK', resp.status)
        self.assert_(WBO.get_time_now() >= float(resp.body))

        resp = self.app.get(storage_url, headers=auth_header, status=404)

    def test_collection_operations(self):
        """Exercise collection counts and timestamps"""
        profile = Profile(user_name = 'tester-1', password = 'pass-1')
        profile.put()

        auth_header = self.build_auth_header(
            profile.user_name, profile.password
        )

        expected_count_all = 0
        expected_counts = {
            'clients':2, 'crypto':0, 'forms':6, 'history':0, 'keys':10,
            'meta':12, 'bookmarks':14, 'prefs':16, 'tabs':18, 'passwords':20,
            'foo':12, 'bar':14, 'baz':16
        }
        expected_dates = {}

        # Insert objects with random contents to satisfy the expected counts
        for collection_name, curr_count in expected_counts.items():
            base_url = '/sync/1.0/%s/storage/%s' % (
                profile.user_name, collection_name
            )
            for i in range(curr_count):
                resp = self.put_random_wbo(base_url, auth_header)
                expected_dates[collection_name] = float(resp.body)
                expected_count_all += 1

        # Ensure the counts match expected
        resp = self.app.get(
            '/sync/1.0/%s/info/collection_counts' % (profile.user_name),
            headers=auth_header
        )
        resp_data = simplejson.loads(resp.body)
        self.assertEqual(expected_counts, resp_data)

        # Ensure all timestamps are same or newer than expected.
        resp = self.app.get(
            '/sync/1.0/%s/info/collections' % (profile.user_name),
            headers=auth_header
        )
        resp_data = simplejson.loads(resp.body)
        for k,v in expected_dates.items():
            self.assert_(k in resp_data)
            self.assert_(resp_data[k] >= expected_dates[k])

        # Verify the count of all objects after creating
        result_count = WBO.all().count()
        self.assertEqual(expected_count_all, result_count)

        # Delete each collection and verify the count after
        for collection_name, curr_count in expected_counts.items():
            url = '/sync/1.0/%s/storage/%s' % (
                profile.user_name, collection_name
            )
            resp = self.app.delete(url, headers=auth_header)
            self.assert_(WBO.get_time_now() >= float(resp.body))

            expected_count_all -= curr_count
            result_count = WBO.all().count()
            self.assertEqual(expected_count_all, result_count)

        # No WBOs should be left after all collections deleted.
        result_count = WBO.all().count()
        self.assertEqual(0, result_count)

    def test_multiple_profiles(self):
        """Exercise multiple profiles and collections"""
        expected_count_all = 0
        profiles_count = 5
        collection_names = ( 'passwords', 'keys', 'tabs', 'history', 'bookmarks' )
        collection_counts = {}

        # Produce a set of Profiles in the datastore
        profiles = []
        for i in range(profiles_count):
            profile = Profile(user_name='t-%s'%i, password='p-%s'%i)
            profile.put()
            profiles.append(profile)

        # Generate collections for each profile.
        for p in profiles:
            auth_header = self.build_auth_header(p.user_name, p.password)
            collection_counts[p.user_name] = {}

            # Run through several collections and make WBOs
            for cn in collection_names:

                curr_count = random.randint(1,10)
                collection_counts[p.user_name][cn] = curr_count
                expected_count_all += curr_count

                # Generate a bunch of random-content WBOs
                base_url = '/sync/1.0/%s/storage/%s' % (p.user_name, cn)
                for i in range(curr_count):
                    resp = self.put_random_wbo(base_url, auth_header)

        # Ensure the total number of WBOs is correct.
        result_count_all = WBO.all().count()
        self.assertEqual(expected_count_all, result_count_all)

        # Ensure the counts for each profile collection matches inserts.
        for profile in profiles:
            counts = Collection.get_counts(profile)
            for name in collection_names:
                c = Collection.get_by_profile_and_name(profile, name)
                self.assertEqual(
                    collection_counts[profile.user_name][name],
                    WBO.get_by_collection(c).count()
                )

        # Delete each of the collections for each user.
        for profile in profiles:
            auth_header = self.build_auth_header(
                profile.user_name, profile.password
            )
            for name in collection_names:
                url = '/sync/1.0/%s/storage/%s' % (profile.user_name, name)
                resp = self.app.delete(url, headers=auth_header)
                # Ensure the individual collection is now empty.
                c = Collection.get_by_profile_and_name(profile, name)
                self.assertEqual(0, WBO.get_by_collection(c).count())

        # Ensure there are no more WBOs
        result_count_all = WBO.all().count()
        self.assertEqual(0, result_count_all)

    def test_range_queries(self):
        """Exercise ranged queries"""
        self.fail("TODO")
        pass

    def put_random_wbo(self, url, auth_header):
        """PUT a randomized WBO, given a base URL and auth header"""
        wbo_id = random.randint(0, 1000000)
        wbo_json = simplejson.dumps({
            'sortindex': random.randint(0, 1000),
            'payload': ''.join(random.sample(string.letters, 16))
        })
        return self.app.put(
            '%s/%s' % (url, wbo_id), 
            headers=auth_header, 
            params=wbo_json
        )

    def build_auth_header(self, user_name=None, passwd=None):
        """Build an HTTP Basic Auth header from user name and password"""
        user_name = user_name or self.USER_NAME
        passwd = passwd or self.PASSWD
        return {
            'Authorization': 'Basic %s' % base64.b64encode(
                '%s:%s' % (user_name, passwd)
            )
        }

