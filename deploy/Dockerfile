FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=dadokdadok.production
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
COPY deploy/requirements.txt deploy/requirements.txt
RUN pip install --no-cache-dir -r deploy/requirements.txt
COPY backend backend
COPY deploy deploy
RUN useradd --uid 10001 --create-home dadok
USER dadok
WORKDIR /app/backend
CMD ["python", "../deploy/start.py"]
