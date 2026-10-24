"""Local Streamlit client for the read-only FastAPI artifact service."""
import os
import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='Retail Forecast · Observed sales',page_icon='◈',layout='wide')
st.markdown('''<style>
.block-container{padding-top:3.6rem;max-width:1450px} h1{letter-spacing:-1.5px}
[data-testid="stMetric"]{background:white;border:1px solid #e2e8ed;border-radius:12px;padding:12px}
[data-testid="stSidebar"]{border-right:1px solid #e2e8ed}
[data-testid="stMetricValue"]{font-size:24px}
.eyebrow{font-size:12px;letter-spacing:2px;color:#107c72;font-weight:700}
</style>''',unsafe_allow_html=True)
API = os.environ.get('RETAIL_API_URL','http://127.0.0.1:8000').rstrip('/')

@st.cache_data(ttl=60,show_spinner=False)
def fetch(route, **params):
    with httpx.Client(timeout=45,trust_env=False) as client:
        response = client.get(API+route,params=params)
    if response.status_code != 200:
        try: detail = response.json().get('detail','Unexpected API response')
        except ValueError: detail = 'Unexpected API response'
        raise ValueError(str(detail))
    return response.json()

def get(route, **params):
    try:
        with st.spinner('Loading saved retail artifacts…'):
            return fetch(route,**params)
    except (httpx.HTTPError,ValueError) as exc:
        st.error(f'Could not load the local API. {exc}')
        st.code('.venv-app/bin/python -m uvicorn retail_forecast.api:app --host 127.0.0.1 --port 8000')
        st.caption('If artifacts are missing, run .venv/bin/python scripts/build_app_bundle.py first. Retry after starting the API.')
        if st.button('Retry connection'):
            fetch.clear(); st.rerun()
        st.stop()

st.markdown('<div class="eyebrow">RETAIL INTELLIGENCE / LOCAL PORTFOLIO DEMO</div>',unsafe_allow_html=True)
st.title('A clearer view of weekly sales')
st.caption('Historical observations, reproducible forecasts and visible uncertainty.')
st.info('Historical dataset · not live retail activity. All forecast dates refer to 2011, not today.')

meta = get('/meta')
with st.sidebar:
    st.markdown('### ◈ Retail Forecast')
    st.caption('OBSERVED SALES EXPLORER')
    st.divider()
    query = st.text_input('Search product ID',placeholder='Try 22423 or 23084',max_chars=80)
    products = get('/products',q=query,limit=200)
    st.caption(f"{products['total']:,} matches · showing up to 200 IDs")
    if not products['products']:
        st.info('No matching products. Clear the search or try another product ID.')
        st.stop()
    product = st.selectbox('Select product',products['products'])
    view = st.radio('Explore', ['Next-week snapshot','Historical backtest','Beyond dataset','Monitoring'])
    st.divider()
    st.caption('UCI Online Retail II\n\nDecember 2009 – December 2011')
    st.caption('Units are observed positive sales after exclusions. They do not establish demand, stockouts or inventory availability.')

if view == 'Monitoring':
    monitor = get('/monitoring')
    st.subheader('Historical monitoring replay')
    st.caption('Simulated delivery timing · real UCI observations · synthetic incidents are stored separately')
    a,b,c = st.columns(3)
    a.metric('Persisted forecasts',f"{monitor['summary']['forecasts']:,}")
    b.metric('Scored weeks',monitor['summary']['scored_weeks'])
    c.metric('Delivery timing','Assumed')
    st.warning(monitor['availability_assumption']+' Distribution changes are investigation signals, not proof of model failure.')
    scores=pd.DataFrame(monitor['scores'])
    if scores.empty: st.info('No closed weeks have been scored yet.')
    else:
        fig=go.Figure(go.Scatter(x=scores.target_week,y=scores.coverage_95*100,mode='lines+markers',name='Observed coverage',line_color='#107c72'))
        fig.add_hline(y=95,line_dash='dash',annotation_text='95% nominal')
        fig.update_layout(title='95% interval coverage over time',yaxis_title='Coverage (%)',height=320,margin=dict(l=0,r=30,t=50,b=0))
        st.plotly_chart(fig,width='stretch')
        st.dataframe(scores[['target_week','rows','mae','wape','coverage_80','coverage_95']],hide_index=True,width='stretch')
    with st.expander('Event history',expanded=True):
        if monitor['events']: st.dataframe(pd.DataFrame(monitor['events'])[['at','week','event','severity']],hide_index=True,width='stretch')
        else: st.info('No monitoring events saved.')
    st.stop()

mode={'Next-week snapshot':'dataset_edge','Historical backtest':'historical','Beyond dataset':'beyond_dataset'}[view]
params={'product_id':product,'mode':mode}
if mode=='historical':
    week=st.selectbox('Historical target week',meta['historical_weeks'],index=len(meta['historical_weeks'])-1)
    params['target_week']=week
    st.caption('Frozen chronological holdout · each forecast used only observations available at its own origin. These are evaluated historical predictions.')
elif mode=='dataset_edge':
    st.caption(f"Next-week snapshot · issued {meta['edge_week']} after the last complete week. Target week is partially covered by the dataset and is not scored.")
else:
    st.subheader('Beyond the dataset')
result=get('/forecast',**params)
if result['status']=='unavailable':
    st.warning(result['reason'])
    if mode=='beyond_dataset': st.caption(f"Last source date: {meta['coverage_end']} · first wholly unsupported target week: {meta['beyond_week']}")
    forecast=None
else:
    forecast=result['forecast']
    st.subheader(f'Product {product} · week of {forecast["target_week"]}')
    a,b,c,d=st.columns(4)
    a.metric('Forecast units',f"{forecast['prediction']:,.1f}")
    b.metric('80% estimated interval',f"{forecast['lower_80']:,.1f} – {forecast['upper_80']:,.1f}")
    c.metric('95% estimated interval',f"{forecast['lower_95']:,.1f} – {forecast['upper_95']:,.1f}")
    d.metric('Actual units', 'Not scored' if forecast['actual'] is None else f"{forecast['actual']:,.0f}")
    st.caption('Intervals are historical residual-based estimates, not guarantees. Time dependence and changing sales patterns can reduce coverage.')

history=get('/history',product_id=product,limit=200)['history']
if history:
    h=pd.DataFrame(history)
    if forecast:
        # Hide observations after a historical origin; target actual is separately identified.
        h=h[h.week.lt(forecast['target_week'])]
    left,right=st.columns([3,1])
    with left:
        st.markdown('#### Weekly observed sales')
        window=st.select_slider('History window',options=[13,26,52,104],value=26)
        shown=h.tail(window)
        fig=go.Figure(go.Scatter(x=shown.week,y=shown.units,mode='lines',name='Observed units',line=dict(color='#107c72',width=2.5),connectgaps=False))
        if forecast:
            f=forecast
            fig.add_trace(go.Scatter(x=[f['target_week']],y=[f['prediction']],mode='markers',name='Forecast + 95% interval',marker=dict(color='#e19332',size=11),error_y=dict(type='data',symmetric=False,array=[f['upper_95']-f['prediction']],arrayminus=[f['prediction']-f['lower_95']],color='#e19332',thickness=3,width=8)))
            if f['actual'] is not None: fig.add_trace(go.Scatter(x=[f['target_week']],y=[f['actual']],mode='markers',name='Target actual',marker=dict(color='#253956',symbol='diamond',size=9)))
        fig.update_layout(height=340,margin=dict(l=0,r=20,t=15,b=0),legend=dict(orientation='h',y=1.15),yaxis_title='Positive sales units',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='white')
        st.plotly_chart(fig,width='stretch')
        st.caption('Unknown and partial weeks remain gaps. Zero units rely on the documented complete-extract assumption.')
    with right:
        st.markdown('#### Baseline comparison')
        if forecast:
            labels={'last_observed_week':'Last observed week','trailing_average':'Trailing 4-week mean','seasonal_naive':'Seasonal naive · 52 weeks'}
            for key,label in labels.items(): st.metric(label,f"{forecast['baselines'][key]:,.1f}")
            if forecast['seasonal_fallback']: st.caption('Seasonal history insufficient: uses trailing 4-week mean.')
        else: st.info('No eligible forecast comparison for this mode/origin.')
else: st.info('No historical weekly observations available for this product.')

with st.expander('Data quality & forecast provenance',expanded=False):
    st.write('Complete-extract assumption:',meta['quality']['assume_complete'])
    st.write('Weekly status counts (whole dataset):',meta['quality']['weekly_status_counts'])
    if forecast:
        st.json({k:forecast[k] for k in ('issue_time','target_week','target_end_exclusive','training_cutoff_exclusive','model_version','data_version')})
        st.caption('Dataset-edge model: separately saved post-evaluation refit. Historical model version: frozen procedure hash plus origin. No training occurs on requests.')
    st.caption('Missing customer IDs do not invalidate product sales. Returns are tracked separately; cancellations, non-product codes and invalid transactions are excluded by the cleaning contract.')
