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

    id_sets = {
        'parentid': ( 
            'a1234','a5678','a5678','a1357','a1357',
            'a1357','a2468','a1000','a9999','a0010'
        ),
        'predecessorid': (
            'b1357','b2468','b1000','b9999','b0010',
            'b1234','b5678','b5678','b1357','b1357'
        )
    }

    def setUp(self):
        """Prepare for unit test"""
        self.log = logging.getLogger()
        self.log.setLevel(logging.DEBUG)
        
        # There shouldn't already be a profile, but just in case...
        profile = Profile.get_by_user_name(self.USER_NAME)
        if profile: profile.delete()

        # Create a new profile for tests.
        self.profile = p = Profile(
            user_name = self.USER_NAME,
            password  = self.PASSWD
        )
        self.profile.put()

        self.auth_header = self.build_auth_header(p.user_name, p.password)

        self.collection = Collection.get_by_profile_and_name(p, 'history')
        
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
        return

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
        return

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

    def test_retrieval_by_id(self):
        """Exercise collection retrieval with a single ID"""
        (p, c, ah) = (self.profile, self.collection, self.auth_header)

        wbo_id = '1234'

        w = WBO(wbo_id=wbo_id, parent=c, collection=c,
            modified=WBO.get_time_now(), sortindex=1000, 
            payload='payload-%s' % wbo_id, payload_size=9)
        w.put()

        url = '/sync/1.0/%s/storage/%s?id=%s' % (
            p.user_name, c.name, w.wbo_id
        )

        resp = self.app.get(url, headers=ah)
        result_data = simplejson.loads(resp.body)
        self.assertEqual(w.wbo_id, result_data[0])

        url = '/sync/1.0/%s/storage/%s?id=%s&full=1' % (
            p.user_name, c.name, w.wbo_id
        )

        resp = self.app.get(url, headers=ah)
        result_data = simplejson.loads(resp.body)
        self.assertEqual(w.payload, result_data[0]['payload'])

    def test_retrieval_by_multiple_ids(self):
        """Exercise collection retrieval with multiple IDs"""
        (p, c, ah) = (self.profile, self.collection, self.auth_header)

        wbos = [ 
            WBO(wbo_id='%s' % wbo_id, parent=c, collection=c,
                modified=WBO.get_time_now(), sortindex=1000, payload='payload-%s' %
                wbo_id, payload_size=9
        ) for wbo_id in range(10) ]

        for w in wbos: w.put()

        wbo_ids = [w.wbo_id for w in wbos]

        url = '/sync/1.0/%s/storage/%s?ids=%s' % (
            p.user_name, c.name, ','.join(wbo_ids)
        )

        resp = self.app.get(url, headers=ah)
        result_data = simplejson.loads(resp.body)
        wbo_ids.sort()
        result_data.sort()
        self.assertEqual(wbo_ids, result_data)

        url = '/sync/1.0/%s/storage/%s?ids=%s&full=1' % (
            p.user_name, c.name, ','.join(wbo_ids)
        )

        resp = self.app.get(url, headers=ah)
        result_data = simplejson.loads(resp.body)
        result_data.sort(lambda a,b: cmp(a['id'], b['id']))
        for idx in range(len(wbos)):
            self.assertEqual(wbos[idx].payload, result_data[idx]['payload'])

    def test_retrieval_by_index_above_and_below(self):
        """Exercise collection retrieval on sortindex range"""
        (p, c, ah) = (self.profile, self.collection, self.auth_header)

        wbo_sortindexes = ( -100, -10, -1, 0, 1, 10, 23, 100, 999, 1000, 9999 )

        wbos = [ ]
        for idx in range(len(wbo_sortindexes)):
            sortindex = wbo_sortindexes[idx]
            wbo_id = '%s' % idx
            w = WBO(wbo_id=wbo_id, parent=c, collection=c,
                modified=WBO.get_time_now(), 
                sortindex=sortindex, 
                payload='payload-%s' % wbo_id, payload_size=9)
            w.put()
            self.log.debug("WBO      %s" % simplejson.dumps(w.to_dict()))
            wbos.append(w)

        # TODO: Try a variety of ranges here?
        (index_above, index_below) = (-10, 1000)

        expected_ids = [
            w.wbo_id for w in wbos
            if index_above < w.sortindex and w.sortindex < index_below
        ]

        url = '/sync/1.0/%s/storage/%s?index_above=%s&index_below=%s' % (
            p.user_name, c.name, index_above, index_below
        )
        resp = self.app.get(url, headers=ah)
        result_data = simplejson.loads(resp.body)

        expected_ids.sort()
        result_data.sort()

        self.log.debug("URL      %s" % url)
        self.log.debug("EXPECTED %s" % simplejson.dumps(expected_ids))
        self.log.debug("RESULT   %s" % resp.body)
        self.assertEqual(expected_ids, result_data)

    def test_retrieval_by_newer_and_older(self):
        """Exercise collection retrieval by modified timestamp range"""
        (p, c, ah) = (self.profile, self.collection, self.auth_header)

        wbos = self.build_wbo_set()

        # TODO: Try a variety of ranges here?
        (newer, older) = (wbos[2].modified, wbos[len(wbos)-2].modified)

        expected_ids = [
            w.wbo_id for w in wbos
            if newer < w.modified and w.modified < older
        ]

        url = '/sync/1.0/%s/storage/%s?newer=%s&older=%s' % (
            p.user_name, c.name, newer, older
        )
        resp = self.app.get(url, headers=ah)
        result_data = simplejson.loads(resp.body)

        expected_ids.sort()
        result_data.sort()

        self.log.debug("URL      %s" % url)
        self.log.debug("EXPECTED %s" % simplejson.dumps(expected_ids))
        self.log.debug("RESULT   %s" % resp.body)
        self.assertEqual(expected_ids, result_data)

    def test_retrieval_by_parent_and_predecessor(self):
        """Exercise collection retrieval by parent and predecessor IDs"""
        (p, c, ah) = (self.profile, self.collection, self.auth_header)

        wbos = self.build_wbo_set()

        for kind, p_ids in self.id_sets.items():
            for p_id in set(p_ids):

                expected_ids = [
                    w.wbo_id for w in wbos
                    if getattr(w, kind) == p_id
                ]

                url = '/sync/1.0/%s/storage/%s?%s=%s' % (
                    p.user_name, c.name, kind, p_id
                )
                resp = self.app.get(url, headers=ah)
                result_data = simplejson.loads(resp.body)

                expected_ids.sort()
                result_data.sort()

                self.log.debug("URL      %s" % url)
                self.log.debug("EXPECTED %s" % simplejson.dumps(expected_ids))
                self.log.debug("RESULT   %s" % resp.body)
                self.assertEqual(expected_ids, result_data)

    def test_retrieval_with_sort(self):
        """Exercise collection retrieval with sort options"""
        (p, c, ah) = (self.profile, self.collection, self.auth_header)

        wbos = self.build_wbo_set()

        sorts = {
            'oldest': lambda a,b: cmp(a.modified,  b.modified),
            'newest': lambda a,b: cmp(b.modified,  a.modified),
            'index':  lambda a,b: cmp(a.sortindex, b.sortindex),
        }

        for sort_option, sort_fn in sorts.items():
            wbos.sort(sort_fn)
            expected_ids = [ w.wbo_id for w in wbos ]

            url = '/sync/1.0/%s/storage/%s?sort=%s' % (
                p.user_name, c.name, sort_option
            )
            resp = self.app.get(url, headers=ah)
            result_data = simplejson.loads(resp.body)

            self.log.debug("URL      %s" % url)
            self.log.debug("EXPECTED %s" % simplejson.dumps(expected_ids))
            self.log.debug("RESULT   %s" % resp.body)
            self.assertEqual(expected_ids, result_data)

    def test_retrieval_with_limit_offset(self):
        """Exercise collection retrieval with limit and offset"""
        (p, c, ah) = (self.profile, self.collection, self.auth_header)

        wbos = self.build_wbo_set()

        max_limit  = len(wbos) / 2
        max_offset = len(wbos) / 2

        for c_limit in range(1, max_limit):
            for c_offset in range(1, max_offset):

                expected_ids = [ 
                    w.wbo_id for w in 
                    wbos[ (c_offset) : (c_offset+c_limit) ] 
                ]

                url = '/sync/1.0/%s/storage/%s?limit=%s&offset=%s&sort=oldest' % (
                    p.user_name, c.name, c_limit, c_offset
                )
                resp = self.app.get(url, headers=ah)
                result_data = simplejson.loads(resp.body)

                self.log.debug("URL      %s" % url)
                self.log.debug("EXPECTED %s" % simplejson.dumps(expected_ids))
                self.log.debug("RESULT   %s" % resp.body)
                self.assertEqual(expected_ids, result_data)

    def test_retrieval_by_multiple_criteria(self):
        """Exercise retrieval when using multiple criteria"""
        (p, c, ah) = (self.profile, self.collection, self.auth_header)

        ids = [ 
            '1', '2', '3', '4', '5', '6', 
            '9', '10', '11', '15', '16' 
        ]
        index_above   = 2
        index_below   = 13
        parentid      = 'a2'
        predecessorid = 'b3'

        value_keys = (
            'expected', 'wbo_id', 'sortindex', 'parentid', 'predecessorid'
        )
        value_sets = (
            (False,  '0',  0, 'a1', 'b3'),
            (False,  '1',  1, 'a1', 'b3'),
            (False,  '2',  2, 'a1', 'b3'),
            (False,  '3',  3, 'a1', 'b3'),
            (False,  '4',  4, 'a1', 'b3'),
            ( True,  '5',  5, 'a2', 'b3'),
            ( True,  '6',  6, 'a2', 'b3'),
            (False,  '7',  7, 'a2', 'b3'),
            (False,  '8',  8, 'a2', 'b3'),
            ( True,  '9',  9, 'a2', 'b3'),
            ( True, '10', 10, 'a2', 'b3'),
            (False, '11', 11, 'a2', 'b1'),
            (False, '12', 12, 'a2', 'b1'),
            (False, '13', 13, 'a3', 'b1'),
            (False, '14', 14, 'a3', 'b1'),
            (False, '15', 15, 'a3', 'b1'),
            (False, '16', 16, 'xx', 'xx'),
        )

        wbos = [ ]
        expected_ids = [ ]
        for idx in range(len(value_sets)):
            values = dict(zip(value_keys, value_sets[idx]))
            
            w = WBO(
                wbo_id=values['wbo_id'], 
                parent=c, collection=c,
                modified=WBO.get_time_now(), 
                parentid=values['parentid'],
                predecessorid=values['predecessorid'],
                sortindex=values['sortindex'], 
                payload='payload-%s' % idx, payload_size=9
            )
            w.put()
            wbos.append(w)

            if values['expected']: 
                expected_ids.append(w.wbo_id)

        params = 'index_above=%s&index_below=%s&parentid=%s&predecessorid=%s&ids=%s' % (
            index_above, index_below, parentid, predecessorid, ','.join(ids)
        )
        url = '/sync/1.0/%s/storage/%s?%s' % (p.user_name, c.name, params)
        resp = self.app.get(url, headers=ah)
        result_data = simplejson.loads(resp.body)

        self.log.debug("URL      %s" % url)
        self.log.debug("EXPECTED %s" % simplejson.dumps(expected_ids))
        self.log.debug("RESULT   %s" % resp.body)
        self.assertEqual(expected_ids, result_data)

#    def test_alternate_output_formats(self):
#        """Exercise alternate output formats for WBOs"""
#        self.fail("TODO")
#
#    def test_bulk_update(self):
#        """Exercise bulk collection update"""
#        self.fail("TODO")
#
#    def test_retrieval_by_direct_output(self):
#        self.fail("TODO")
#

    def build_wbo_set(self, num_wbos=15):
        (p, c, ah) = (self.profile, self.collection, self.auth_header)

        num_wbos = 10

        wbos = [ ]
        for idx in range(num_wbos):
            w = WBO(wbo_id='%s' % idx, parent=c, collection=c,
                modified=WBO.get_time_now(), 
                parentid=self.id_sets['parentid'][idx],
                predecessorid=self.id_sets['predecessorid'][idx],
                sortindex=random.randint(0,100000), 
                payload='payload-%s' % idx, payload_size=9)
            w.put()
            wbos.append(w)
            # HACK: Delay to ensure modified stamps vary
            time.sleep(0.1)
        return wbos

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

