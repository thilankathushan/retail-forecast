import tempfile
from pathlib import Path
import unittest
import pandas as pd
import numpy as np
from retail_forecast.tree import features, fit_at, predict_at, save_model, reload_model, FEATURES

class TreeTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame([{'product_id':p,'week_start':w,'observed_units':float(i%9), 'status':'observed'}
                             for p in ['A','B'] for i,w in enumerate(pd.date_range('2024-01-01', periods=20, freq='7D'))])

    def test_features_and_predictions_ignore_future(self):
        frame = self.frame()
        origin = pd.Timestamp('2024-03-04')
        a = features(frame, '2024-01-01', '2024-05-13')
        changed = frame.copy()
        changed.loc[changed.week_start.ge(origin), 'observed_units'] = 9999
        b = features(changed, '2024-01-01', '2024-05-13')
        pd.testing.assert_frame_equal(a[a.week_start.le(origin)][FEATURES], b[b.week_start.le(origin)][FEATURES])
        config = {'max_iter':3,'max_leaf_nodes':3}
        ma,_ = fit_at(a, origin, config)
        mb,_ = fit_at(b, origin, config)
        np.testing.assert_array_equal(predict_at(ma,a,origin).prediction, predict_at(mb,b,origin).prediction)
        row = a[(a.product_id=='A') & a.week_start.eq('2024-01-29')].iloc[0]
        self.assertEqual(row.lag_1,3)
        self.assertEqual(row.mean_4,1.5)
        self.assertEqual(row.history_observed,4)
        self.assertEqual(row.history_active,3)
        # Inference without any target rows follows exactly the historical feature path.
        inference = features(frame[frame.week_start.lt(origin)],'2024-01-01',origin)
        pd.testing.assert_frame_equal(a[a.week_start.eq(origin)][FEATURES].reset_index(drop=True),
                                       inference[inference.week_start.eq(origin)][FEATURES].reset_index(drop=True))

    def test_reload_and_unseen_products(self):
        table = features(self.frame(),'2024-01-01','2024-05-13')
        origin = pd.Timestamp('2024-04-01')
        model,_ = fit_at(table,origin,{'max_iter':3,'max_leaf_nodes':3})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'model.joblib'
            save_model(model,path,{'training_end_exclusive':str(origin.date())})
            loaded,_ = reload_model(path)
            np.testing.assert_array_equal(predict_at(model,table,origin).prediction,predict_at(loaded,table,origin).prediction)
            path.write_bytes(b'corrupt')
            with self.assertRaises(ValueError): reload_model(path)
        renamed = self.frame().assign(product_id=lambda f: f.product_id+'UNSEEN')
        new = features(renamed,'2024-01-01','2024-05-13')
        np.testing.assert_array_equal(predict_at(model,table,origin).prediction,predict_at(model,new,origin).prediction)
