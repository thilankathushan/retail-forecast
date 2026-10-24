"""Fixed, historical OOS normalized-residual intervals."""
import math
import numpy as np

LEVELS = (0.8, 0.95)


def scales(mean13):
    values = np.asarray(mean13, dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('Interval scales require finite nonnegative historical means')
    return np.maximum(1.0, values)


def calibrate(actual, predicted, scale, levels=LEVELS):
    actual, predicted, scale = map(lambda x: np.asarray(x, dtype=float), (actual, predicted, scale))
    if not (actual.shape == predicted.shape == scale.shape) or not len(actual):
        raise ValueError('Calibration arrays must be aligned and nonempty')
    if any(not np.isfinite(x).all() for x in (actual, predicted, scale)) or (scale < 1).any():
        raise ValueError('Calibration needs finite values and scales at least one')
    if (actual < 0).any() or (predicted < 0).any():
        raise ValueError('Sales and predictions must be nonnegative')
    scores = np.sort(np.abs(actual-predicted)/scale)
    result = {}
    for level in levels:
        if not 0 < level < 1:
            raise ValueError('Nominal coverage must lie strictly between zero and one')
        rank = math.ceil((len(scores)+1)*level)
        if rank > len(scores):
            raise ValueError('Too few calibration rows for a finite corrected quantile')
        result[str(level)] = {'quantile': float(scores[rank-1]), 'rank': rank}
    return {'rows': len(scores), 'levels': result, 'method': 'pooled historical OOS absolute error / max(1, prior mean13)'}


def bounds(prediction, scale, quantile):
    prediction, scale = np.asarray(prediction, dtype=float), np.asarray(scale, dtype=float)
    if prediction.shape != scale.shape or not np.isfinite(prediction).all() or (prediction < 0).any():
        raise ValueError('Invalid interval prediction inputs')
    if not np.isfinite(scale).all() or (scale < 1).any() or not math.isfinite(quantile) or quantile < 0:
        raise ValueError('Invalid scale or quantile')
    return np.maximum(0, prediction-quantile*scale), prediction+quantile*scale


def interval_metrics(actual, lower, upper, level):
    a, lo, hi = map(lambda x: np.asarray(x,dtype=float), (actual,lower,upper))
    if not (a.shape == lo.shape == hi.shape) or (lo > hi).any() or not 0 < level < 1:
        raise ValueError('Invalid interval metric arrays or coverage')
    if any(not np.isfinite(x).all() for x in (a,lo,hi)):
        raise ValueError('Non-finite interval metrics input')
    if not len(a):
        return {'rows':0,'coverage':None,'mean_width':None,'median_width':None,'mean_interval_score':None}
    width = hi-lo
    score = width + 2/(1-level)*(np.maximum(lo-a,0)+np.maximum(a-hi,0))
    return {'rows':len(a),'coverage':float(((a>=lo)&(a<=hi)).mean()),
            'mean_width':float(width.mean()),'median_width':float(np.median(width)),
            'mean_interval_score':float(score.mean())}
