FROM python:3.9-slim

# System deps for WeasyPrint (pango, cairo) and Kaleido/Chromium (chart rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 libffi-dev libcairo2 \
    fonts-liberation fonts-dejavu-core \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Tell Kaleido/Plotly where Chromium lives
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMIUM_FLAGS="--no-sandbox --disable-gpu"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 3001
CMD sh -c "gunicorn --bind 0.0.0.0:${PORT:-3001} --timeout 300 --workers 1 app:app"
