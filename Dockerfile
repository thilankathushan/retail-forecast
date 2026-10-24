FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
WORKDIR /app
COPY requirements-app.txt requirements-app-lock.txt ./
RUN pip install --no-cache-dir -c requirements-app-lock.txt -r requirements-app.txt \
    && pip check \
    && useradd --uid 10001 --create-home appuser
COPY retail_forecast/__init__.py retail_forecast/api.py ./retail_forecast/
COPY dashboard.py ./
COPY .streamlit/config.toml ./.streamlit/config.toml
USER 10001:10001
EXPOSE 8000 8501
CMD ["python", "-m", "uvicorn", "retail_forecast.api:app", "--host", "0.0.0.0", "--port", "8000"]
