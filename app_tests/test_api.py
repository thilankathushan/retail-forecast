"""API contract tests use a tiny fictional bundle, never benchmark data."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from retail_forecast.api import create_app


def fixture():
    f={'product_id':'TEST-A','mode':'dataset_edge','target_week':'2024-02-05',
        'issue_time':'2024-02-05T00:00:00+00:00','target_end_exclusive':'2024-02-12',
        'training_cutoff_exclusive':'2024-02-05','prediction':10,'actual':None,
        'lower_80':8,'upper_80':12,'lower_95':5,'upper_95':15,
        'baselines':{'last_observed_week':9,'trailing_average':8,'seasonal_naive':8},
        'seasonal_fallback':True,'model_version':'fictional-model','data_version':'fictional-data'}
    historical=f | {'mode':'historical','actual':11}
    return {'schema_version':1,'built_at':'2024-03-01T00:00:00Z','coverage_start':'2024-01-01',
        'coverage_end':'2024-02-09','edge_week':'2024-02-05','beyond_week':'2024-02-12',
        'data_version':'fictional-data','freeze_version':'fictional-freeze','quality':{},
        'history':{'TEST-A':[{'week':'2024-01-29','units':9,'status':'observed'},
            {'week':'2024-02-05','units':None,'status':'partial_week'}], 'TEST-B':[]},
        'forecasts':[f,historical], 'monitoring':{'summary':{},'events':[],'scores':[]}}

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'bundle.json'
        self.write(fixture())
        self.client=TestClient(create_app(self.path))
        self.addCleanup(self.client.close)

    def write(self,value):
        raw=json.dumps(value).encode();self.path.write_bytes(raw)
        self.path.with_name('manifest.json').write_text(json.dumps({'bundle_sha256':hashlib.sha256(raw).hexdigest()}))

    def test_search_is_literal_and_bounded(self):
        self.assertEqual(self.client.get('/products',params={'q':'test-a'}).json()['products'],['TEST-A'])
        self.assertEqual(self.client.get('/products',params={'q':'.*'}).json()['total'],0)
        for params in ({'limit':201},{'q':'a'*81}):
            self.assertEqual(self.client.get('/products',params=params).status_code,422)

    def test_forecast_contract_and_unknown_observations(self):
        result=self.client.get('/forecast',params={'product_id':'TEST-A'}).json()
        self.assertEqual(result['status'],'available')
        f=result['forecast'];self.assertIsNone(f['actual']);self.assertEqual(f['prediction'],10)
        self.assertEqual(f['baselines']['seasonal_naive'],8)
        self.assertEqual(self.client.get('/history',params={'product_id':'TEST-A'}).json()['history'][-1]['units'],None)
        historical=self.client.get('/forecast',params={'product_id':'TEST-A','mode':'historical'}).json()
        self.assertEqual(historical['forecast']['actual'],11)

    def test_unavailable_is_not_zero_forecast(self):
        for params in ({'product_id':'TEST-A','mode':'beyond_dataset'},{'product_id':'TEST-B'}):
            body=self.client.get('/forecast',params=params).json()
            self.assertEqual(body['status'],'unavailable');self.assertIsNone(body['forecast']);self.assertTrue(body['reason'])

    def test_bad_requests_and_unknown_products(self):
        for params in ({'product_id':'../secrets'},{'product_id':'TEST-A','mode':'live'},
                       {'product_id':'TEST-A','target_week':'2024-02-06'},
                       {'product_id':'TEST-A','target_week':'today'}):
            self.assertEqual(self.client.get('/forecast',params=params).status_code,422)
        self.assertEqual(self.client.get('/forecast',params={'product_id':'UNKNOWN'}).status_code,404)
        self.assertEqual(self.client.get('/forecast',params={'product_id':'TEST-A','mode':'historical','target_week':'2024-02-12'}).status_code,404)

    def test_missing_corrupt_and_invalid_artifacts_are_actionable(self):
        for mutation in ('missing','hash','interval','duplicate'):
            with self.subTest(mutation=mutation):
                data=fixture()
                if mutation=='interval':data['forecasts'][0]['lower_95']=99
                if mutation=='duplicate':data['forecasts'].append(copy.deepcopy(data['forecasts'][0]))
                self.write(data)
                if mutation=='missing':self.path.unlink()
                if mutation=='hash':self.path.write_text('{}')
                with TestClient(create_app(self.path)) as client:
                    result=client.get('/meta')
                    self.assertEqual(result.status_code,503)
                    self.assertIn('build_app_bundle.py',result.json()['detail'])

    def test_empty_historical_folds_are_unavailable(self):
        data=fixture()
        data['forecasts']=[data['forecasts'][0]]
        self.write(data)
        response=self.client.get('/forecast',params={'product_id':'TEST-A','mode':'historical'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'unavailable')
        self.assertIsNone(response.json()['forecast'])

    def test_read_only_and_cached(self):
        self.client.get('/meta')
        self.path.unlink()
        self.assertEqual(self.client.get('/meta').status_code,200)
        self.assertEqual(self.client.post('/forecast').status_code,405)
        self.assertEqual(self.client.get('/monitoring').json()['simulation'],True)

if __name__=='__main__':unittest.main()
