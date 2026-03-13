FROM python:3.9-slim

# System deps for WeasyPrint (pango, cairo) and Kaleido (chromium libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev libcairo2 \
    fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 3001
CMD ["gunicorn", "--bind", "0.0.0.0:3001", "--timeout", "120", "--workers", "2", "app:app"]
