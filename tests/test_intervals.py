import unittest
import numpy as np
import pandas as pd
from retail_forecast.intervals import calibrate, bounds, scales, interval_metrics
from retail_forecast.final_evaluation import forecast_origin, segment


class IntervalTests(unittest.TestCase):
    def test_corrected_quantiles_and_scale_invariance(self):
        actual=np.arange(1,20,dtype=float)
        c=calibrate(actual,np.zeros(19),np.ones(19))
        self.assertEqual(c['levels']['0.8']['rank'],16)
        self.assertEqual(c['levels']['0.8']['quantile'],16)
        self.assertEqual(c['levels']['0.95']['quantile'],19)
        self.assertEqual(c,calibrate(actual*10,np.zeros(19),np.ones(19)*10))
        with self.assertRaises(ValueError):calibrate([1],[0],[1])
        np.testing.assert_array_equal(scales([0,0.1,5]),[1,1,5])

    def test_interval_metrics_and_nonnegative_bounds(self):
        lo,hi=bounds([1,10],[1,2],3)
        np.testing.assert_array_equal(lo,[0,4])
        np.testing.assert_array_equal(hi,[4,16])
        result=interval_metrics([0,20],lo,hi,0.8)
        self.assertEqual(result['coverage'],0.5)
        self.assertEqual(result['mean_width'],8)
        self.assertAlmostEqual(result['mean_interval_score'],28)
        self.assertEqual(interval_metrics([0],[0],[0],0.95)['coverage'],1)
        with self.assertRaises(ValueError):bounds([1],[0],1)

    def test_final_origin_uses_only_history_and_matches_baselines(self):
        dates=pd.date_range('2024-01-01',periods=12,freq='7D')
        frame=pd.DataFrame({'week_start':dates,'product_id':['A']*12,
                            'observed_units':np.arange(12,dtype=float),'status':['observed']*12})
        spec={'protocol':{'train_start':'2024-01-01','min_history_weeks':4,'seasonal_weeks':52},
              'configuration':{'max_iter':3,'max_leaf_nodes':3},'seed':42}
        origin=dates[-1]+pd.Timedelta(weeks=1)
        result,meta,_=forecast_origin(frame,origin,spec)
        self.assertEqual(result.iloc[0].last_observed_week,11)
        self.assertEqual(result.iloc[0].trailing_average,9.5)
        self.assertEqual(result.iloc[0].seasonal_naive,9.5)
        self.assertTrue(result.iloc[0].seasonal_fallback)
        self.assertEqual(result.iloc[0].history_segment,'4-12')
        self.assertEqual(result.iloc[0].scale,5.5)
        contaminated=pd.concat([frame,pd.DataFrame({'week_start':[origin],'product_id':['A'],
                                                   'observed_units':[999],'status':['observed']})])
        with self.assertRaises(ValueError):forecast_origin(contaminated,origin,spec)

    def test_segments_use_only_historical_values(self):
        f=pd.DataFrame({'history_observed':[0,3,4,13,52],'history_active':[0,1,0,1,2],
                        'mean_13':[0,2,5,25,26]})
        s=segment(f)
        self.assertEqual(s.history_segment.tolist(),['0','1-3','4-12','13-51','52+'])
        self.assertEqual(s.scale_segment.tolist(),['<=5','<=5','<=5','5-25','>25'])
