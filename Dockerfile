# =============================================================================
# Dockerfile - PanganPintar API
# Multi-stage build untuk deployment ke HuggingFace Spaces (Docker template)
# =============================================================================

# --- Stage 1: Builder ---
# Menggunakan stage terpisah untuk install dependencies agar layer cache optimal
FROM python:3.13-slim AS builder

WORKDIR /build

# Install dependencies terlebih dahulu (layer caching)
# Layer ini hanya rebuild kalau requirements.txt berubah
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.13-slim AS runtime

# Install curl untuk health check
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Buat non-root user sesuai requirement HuggingFace Spaces
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy installed packages dari builder stage
COPY --from=builder /install /usr/local

# Copy seluruh source code dan artifacts ke dalam image
COPY . .

# Set ownership agar non-root user bisa akses file aplikasi
RUN chown -R appuser:appuser /app

# Environment variables untuk runtime
# HF_HOME diarahkan ke /tmp agar model cache HuggingFace tidak error permission
ENV HF_HOME=/tmp \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose port default HuggingFace Spaces
EXPOSE 7860

# Health check menggunakan curl ke /health endpoint
# Interval 30 detik, timeout 10 detik, retry 3x sebelum dianggap unhealthy
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Gunakan non-root user untuk menjalankan aplikasi
USER appuser

# Jalankan FastAPI via uvicorn pada port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
