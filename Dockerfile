# 1. Imagem base leve com Python 3.11
FROM python:3.11-slim

# 2. Define o diretório de trabalho dentro do container
WORKDIR /app

# 3. Instala as dependências do sistema operacional
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libpango-1.0-0 \
    libharfbuzz0b \
    libfribidi0 \
    libjpeg62-turbo \
    libopenjp2-7 \
    libtiff6 \
    libgl1 \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# 4. Copia e instala as dependências Python
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Copia todo o código da aplicação
COPY . .

# 6. Define a variável de ambiente FLASK_CONFIG para produção
ENV FLASK_CONFIG=production

# 7. Expõe a porta que o Cloud Run espera (Gunicorn usará a var $PORT)
EXPOSE 8080

# 8. Define o comando de entrada para iniciar o Gunicorn.
# O wsgi:application aponta para o arquivo wsgi.py e a variável 'application'.
CMD exec gunicorn --bind :$PORT --workers 1 --worker-tmp-dir /dev/shm --timeout 300 wsgi:application
