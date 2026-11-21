
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt

# Install CPU-only PyTorch
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["sh", "-c", "python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
