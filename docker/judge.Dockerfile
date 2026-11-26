# Judge-like image for local testing only (the organizers use their own).
FROM python:3.11-slim
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir numpy scipy pandas xarray scikit-learn lightgbm onnxruntime fastapi flask uvicorn gunicorn
WORKDIR /sub
