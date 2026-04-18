FROM python:3.11-slim

# Metadados
LABEL maintainer="Kindle Highlights Extractor"
LABEL description="Interface Streamlit para extração de destaques do Kindle"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Define diretório de trabalho
WORKDIR /app

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY . .

# Cria diretórios necessários
RUN mkdir -p /app/data /app/output /app/logs

# Expõe porta
EXPOSE 8501

# Comando de inicialização
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true"]