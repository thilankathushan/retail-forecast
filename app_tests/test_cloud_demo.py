import unittest
from retail_forecast.cloud_demo import fetch
class CloudDemoTests(unittest.TestCase):
    def test_real_archive_modes(self):
        self.assertEqual(fetch('/products',q='22423')['products'],['22423'])
        edge=fetch('/forecast',product_id='22423')['forecast']
        self.assertEqual(edge['target_week'],'2011-12-05');self.assertIsNone(edge['actual'])
        past=fetch('/forecast',product_id='22423',mode='historical',target_week='2011-11-28')['forecast']
        self.assertEqual(past['actual'],236)
        self.assertEqual(fetch('/forecast',product_id='22423',mode='beyond_dataset')['status'],'unavailable')
        self.assertEqual(fetch('/products',q='../')['total'],0)
        self.assertTrue(fetch('/monitoring')['simulation'])
