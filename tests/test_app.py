import json
import os
from unittest import TestCase

from chalice.config import Config
from chalice.local import LocalGateway

from app import app, ESConnection

DEFAULT_HOST = 'search-dss-azul-commons-lx3ltgewjw5wiw2yrxftoqr7jy.us-west-2.es.amazonaws.com'  # NOQA
DEFAULT_REGION = 'us-west-2'
DEFAULT_INDEX = 'fb_index'
DEFAULT_DOCTYPE = 'meta'

es_index = os.environ.get('ES_INDEX', DEFAULT_INDEX)
es_host = os.environ.get('ES_HOST', DEFAULT_HOST)
es_region = os.environ.get('ES_REGION', DEFAULT_REGION)
es_doctype = os.environ.get('ES_DOCTYPE', DEFAULT_DOCTYPE)
client = ESConnection(
    region=es_region, host=es_host, is_secure=False)

class TestApp(TestCase):
    def setUp(self):
        self.lg = LocalGateway(app, Config())

    def test_get_root(self):
        """
        Tests to see we can access the ES instance.

        :return:
        """
        response = self.lg.handle_request(
            method='GET',
            path='/',
            headers={},
            body='')
        self.assertEquals(response['statusCode'], 200)
        body_keys = json.loads(response['body']).keys()
        self.assertIn('version', body_keys)

    def test_list_data_objects(self):
        """
        Test the listing feature returns a response.

        :return:
        """
        page_size = 10
        response = self.lg.handle_request(
            method='POST',
            path='/ga4gh/dos/v1/dataobjects/list',
            headers={'content-type': 'application/json'},
            body=json.dumps({'page_size': page_size}))

        self.assertEquals(response['statusCode'], 200)
        response_body = json.loads(response['body'])
        self.assertEquals(len(response_body['data_objects']), page_size)

    def test_get_data_object(self):
        """
        Lists Data Objects and then gets one by ID.
        :return:
        """
        list_response = self.lg.handle_request(
            method='POST',
            path='/ga4gh/dos/v1/dataobjects/list',
            headers={'content-type': 'application/json'},
            body=json.dumps({}))

        data_objects = json.loads(list_response['body'])['data_objects']
        data_object_id = data_objects[0]['id']
        response = self.lg.handle_request(
            method='GET',
            path='/ga4gh/dos/v1/dataobjects/{}'.format(data_object_id),
            headers={},
            body='')
        self.assertEquals(response['statusCode'], 200)
        data_object = json.loads(response['body'])['data_object']
        self.assertEquals(data_object['id'], data_object_id)

    def test_paging(self):
        """
        Demonstrates basic paging features.

        :return:
        """
        body = {
            'alias': 'specimenUUID:d842b267-a154-5192-988b-b9f9f0265840',
            'page_size': 1}
        list_response = self.lg.handle_request(
            method='POST',
            path='/ga4gh/dos/v1/dataobjects/list',
            headers={'content-type': 'application/json'},
            body=json.dumps(body))
        response_body = json.loads(list_response['body'])
        data_objects = response_body['data_objects']

        self.assertEquals(len(data_objects), 1)

        self.assertEquals(response_body['next_page_token'], '1')

        body = {
            'alias': 'specimenUUID:d842b267-a154-5192-988b-b9f9f0265840',
            'page_size': 1,
            'page_token': response_body['next_page_token']}
        list_response = self.lg.handle_request(
            method='POST',
            path='/ga4gh/dos/v1/dataobjects/list',
            headers={'content-type': 'application/json'},
            body=json.dumps(body))
        response_body = json.loads(list_response['body'])
        data_objects = response_body['data_objects']

        self.assertEquals(len(data_objects), 1)

    def test_update(self):
        """
        Demonstrates how updating a Data Object should work to
        include new fields. The lambda handles the conversion
        to the original document type.

        :return:
        """
        my_guid = 'doi:MY-IDENTIFIER'
        # First get an object to update
        body = {
            'alias': 'specimenUUID:d842b267-a154-5192-988b-b9f9f0265840',
            'page_size': 1}
        list_response = self.lg.handle_request(
            method='POST',
            path='/ga4gh/dos/v1/dataobjects/list',
            headers={'content-type': 'application/json'},
            body=json.dumps(body))
        self.assertEquals(list_response['statusCode'], 200)
        response_body = json.loads(list_response['body'])
        data_objects = response_body['data_objects']
        data_object = data_objects[0]

        # First we'll try to update something with no new
        # information, this is a noop and will return 200.

        url = '/ga4gh/dos/v1/dataobjects/{}'.format(data_object['id'])
        update_response = self.lg.handle_request(
            method='PUT',
            path=url,
            headers={'content-type': 'application/json'},
            body=json.dumps(data_object))
        self.assertEquals(update_response['statusCode'], 200)

        # Make sure it doesn't already include the GUID
        self.assertNotIn(my_guid, data_object['aliases'])

        # Next, we'll try to update with a "protected key", i.e.
        # a value that has already been set on an item that is
        # not in the "whitelist".

        data_object['aliases'].append('file_id:GARBAGEID')

        url = '/ga4gh/dos/v1/dataobjects/{}'.format(data_object['id'])
        update_response = self.lg.handle_request(
            method='PUT',
            path=url,
            headers={'content-type': 'application/json'},
            body=json.dumps(data_object))
        self.assertEquals(update_response['statusCode'], 400)

        # Remove that "bad alias".
        data_object['aliases'] = data_object['aliases'][:-1]

        # Modify to include a GUID
        data_object['aliases'].append(my_guid)

        # Make an update request
        url = '/ga4gh/dos/v1/dataobjects/{}'.format(data_object['id'])
        update_request = data_object
        update_response = self.lg.handle_request(
            method='PUT',
            path=url,
            headers={'content-type': 'application/json'},
            body=json.dumps(update_request))
        self.assertEquals(update_response['statusCode'], 200)
        update_response_body = json.loads(update_response['body'])
        self.assertEqual(
            data_object['id'], update_response_body['data_object_id'])

        # Now get it again to verify it is there
        get_response = self.lg.handle_request(
            method='GET',
            path=url,
            headers={},
            body='')
        self.assertEquals(get_response['statusCode'], 200)
        get_response_body = json.loads(get_response['body'])
        got_data_object = get_response_body['data_object']
        self.assertEqual(
            update_response_body['data_object_id'],
            got_data_object['id'])
        self.assertIn(my_guid, got_data_object['aliases'])

        # Lastly, modify the value so we can rerun tests on the
        # same object
        data_object['aliases'][-1] = "doi:abc"
        update_response = self.lg.handle_request(
            method='PUT',
            path=url,
            headers={'content-type': 'application/json'},
            body=json.dumps(data_object))
        self.assertEquals(update_response['statusCode'], 200)
        update_response_body = json.loads(update_response['body'])
        self.assertEqual(
            data_object['id'], update_response_body['data_object_id'])


        # Now get it again to verify it is gone
        get_response = self.lg.handle_request(
            method='GET',
            path=url,
            headers={},
            body='')
        self.assertEquals(get_response['statusCode'], 200)
        get_response_body = json.loads(get_response['body'])
        got_data_object = get_response_body['data_object']
        self.assertEqual(
            update_response_body['data_object_id'],
            got_data_object['id'])
        self.assertNotIn(my_guid, got_data_object['aliases'])
