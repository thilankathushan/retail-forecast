"""Descriptive frozen-holdout plots; never used to tune the frozen procedure."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/retail-matplotlib')
from pathlib import Path
import json
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

source=Path('artifacts/uci/final')
out=Path('reports/final');out.mkdir(exist_ok=True,parents=True)
report=json.loads((source/'metrics.json').read_text())
pred=pd.read_csv(source/'predictions.csv',dtype={'product_id':str})
scored=pred[pred.scored].copy()
colors={'tree':'#167d8d','last_observed_week':'#8c6bb1','trailing_average':'#d67a24','seasonal_naive':'#87929b'}
labels={'tree':'Global tree','last_observed_week':'Last week','trailing_average':'Trailing average','seasonal_naive':'Seasonal + fallback'}
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
fig,ax=plt.subplots(1,2,figsize=(12,4.4),layout='constrained')
fold=pd.read_csv(source/'point_by_issue_week.csv')
for model in colors:
 g=fold[fold.model.eq(model)]
 ax[0].plot(pd.to_datetime(g.issue_week),g.mae,label=labels[model],color=colors[model],marker='o',markersize=3)
ax[0].set(title='Final holdout: weekly MAE',ylabel='Absolute error per product-week (units)')
ax[0].tick_params(axis='x',rotation=35);ax[0].legend(fontsize=8)
models=list(colors)
ax[1].barh([labels[m] for m in models],[report['point'][m]['wape']*100 for m in models],color=[colors[m] for m in models])
ax[1].set(title='Same scored observations for every model',xlabel='Aggregate WAPE (%)')
fig.savefig(out/'point_accuracy.png',dpi=160);plt.close(fig)
fig,ax=plt.subplots(1,2,figsize=(12,4.4),layout='constrained')
interval=pd.read_csv(source/'interval_by_scale_segment.csv')
segments=['<=5','5-25','>25']
x=np.arange(3)
for i,(level,color) in enumerate([(0.8,'#167d8d'),(0.95,'#d67a24')]):
 g=interval[interval.level.eq(level)].set_index('scale_segment').reindex(segments)
 ax[0].bar(x+(i-.5)*.35,g.coverage*100,width=.35,color=color,label=f'{level:.0%} nominal')
 ax[0].axhline(level*100,color=color,linestyle='--',linewidth=1)
 ax[1].bar(x+(i-.5)*.35,g.mean_width,width=.35,color=color,label=f'{level:.0%} interval')
for a in ax:a.set_xticks(x,segments);a.set_xlabel('Origin-time historical scale (units)');a.legend(fontsize=8)
ax[0].set(title='Empirical interval coverage by sales scale',ylabel='Covered product-weeks (%)',ylim=(0,103))
ax[1].set(title='Interval width by sales scale',ylabel='Mean interval width (units)')
fig.savefig(out/'interval_diagnostics.png',dpi=160);plt.close(fig)
scored['absolute_error']=(scored.actual-scored.tree).abs()
scored.nlargest(20,'absolute_error').to_csv(source/'largest_errors.csv',index=False)
products=scored.nlargest(20,'absolute_error').product_id.drop_duplicates().head(3)
fig,axes=plt.subplots(len(products),1,figsize=(11,8),layout='constrained',squeeze=False)
for axis,product in zip(axes[:,0],products):
 g=scored[scored.product_id.eq(product)].sort_values('issue_week');dates=pd.to_datetime(g.issue_week)
 axis.fill_between(dates,g['lower_0.95'],g['upper_0.95'],alpha=.2,color='#167d8d',label='95% interval')
 axis.plot(dates,g.actual,color='#252525',marker='o',markersize=3,label='Observed sales')
 axis.plot(dates,g.tree,color='#167d8d',label='Tree forecast')
 axis.set(title=f'Product {product} — chosen after evaluation for largest-error inspection',ylabel='Units');axis.legend(fontsize=8)
fig.savefig(out/'largest_error_examples.png',dpi=160);plt.close(fig)
for name in ['metrics.json','runtime.csv','point_by_history_segment.csv','point_by_scale_segment.csv','point_by_activity_segment.csv',
             'interval_by_history_segment.csv','interval_by_scale_segment.csv','interval_by_activity_segment.csv','point_by_issue_week.csv','interval_by_issue_week.csv']:
 shutil.copyfile(source/name,out/name)
print('Saved final evaluation plots and summary tables to',out)
