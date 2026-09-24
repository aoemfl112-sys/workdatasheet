FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WORKSHEET_SERVER=1
ENV TZ=Asia/Seoul

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py SERVER_MODE ./
COPY engine ./engine
COPY config ./config
COPY templates ./templates
COPY .streamlit ./.streamlit

RUN mkdir -p output saved_layouts

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"

# 서버 주소·포트 등은 .streamlit/config.toml 에 있다.
CMD ["python", "-m", "streamlit", "run", "app.py"]
