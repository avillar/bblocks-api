FROM python:3.10-alpine
EXPOSE 5000

WORKDIR /app

COPY requirements.txt .
RUN apk update && \
    apk add git && \
    python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY ogc/ ./ogc/
EXPOSE 5000
ENTRYPOINT ["uvicorn", "ogc.bblocks.app:app", "--reload", "--host", "0.0.0.0", "--port", "5000"]