# ==============================================================================
# Jellyfish OS — Dockerfile Multi-Stage de Producción Aislado
# ==============================================================================

# --- Stage 1: Build & Dependencies ---
FROM python:3.11-slim AS builder

WORKDIR /build

# Instalar dependencias del sistema requeridas para compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear entorno virtual e instalar dependencias
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --upgrade pip && \
    if [ -f requirements.lock ]; then \
        pip install --no-cache-dir -r requirements.lock; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# --- Stage 2: Final Production Environment ---
FROM python:3.11-slim AS runner

# Crear usuario no privilegiado para ejecución segura
RUN groupadd -g 1000 jellyfishgroup && \
    useradd -u 1000 -g jellyfishgroup -m -s /bin/bash jellyfishuser

WORKDIR /app

# Instalar runtime básico
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copiar virtualenv del stage builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copiar el código fuente del proyecto Jellyfish OS
COPY --chown=jellyfishuser:jellyfishgroup . /app

# Crear directorio de trabajo para proyectos
RUN mkdir -p /app/projects && chown -R jellyfishuser:jellyfishgroup /app

USER jellyfishuser

# Exponer volumen para proyectos persistentes
VOLUME ["/app/projects"]

CMD ["python3", "jellyfish.py"]
