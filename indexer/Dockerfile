FROM python:3.11-slim-bookworm

ARG USERID=1111
ARG GROUPID=1111

RUN groupadd -g ${USERID} app && \
    useradd -g ${GROUPID} -u ${USERID} -d /app/ -m -s /bin/bash app

WORKDIR /app/

USER app

COPY requirements.txt requirements.txt
COPY indexer indexer/

RUN pip install -U -r requirements.txt

CMD python3 -m fastapi run ./indexer/indexer.py
