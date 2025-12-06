
FROM python:3.12-slim

WORKDIR /app


COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir honcho

COPY . .

EXPOSE 8000

CMD ["honcho", "start"]