FROM node:20-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm install

COPY python/requirements.txt ./python/requirements.txt
RUN python3 -m pip install --break-system-packages -r python/requirements.txt

COPY . .

ENV PYTHONPATH=/app/python
ENV AIMIPAY_REPOSITORY_ROOT=/app
ENV AIMIPAY_FULL_HOST=http://127.0.0.1:9090
ENV AIMIPAY_SETTLEMENT_BACKEND=local_smoke
ENV AIMIPAY_CHAIN_ID=31337
ENV AIMIPAY_MERCHANT_PORT=8000
ENV AIMIPAY_SELLER_ADDRESS=0x70997970C51812dc3A010C7d01b50e0d17dc79C8
ENV AIMIPAY_SELLER_PRIVATE_KEY=seller_private_key
ENV AIMIPAY_CONTRACT_ADDRESS=TRX_CONTRACT
ENV AIMIPAY_TOKEN_ADDRESS=TRX_USDT
ENV AIMIPAY_SQLITE_PATH=/app/python/.docker-local/payments.db

RUN mkdir -p /app/python/.docker-local

CMD ["python3", "-m", "uvicorn", "python.examples.merchant_app:app", "--host", "0.0.0.0", "--port", "8000"]
