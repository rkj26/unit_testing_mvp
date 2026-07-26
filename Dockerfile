FROM python:3.11.13-slim-bookworm AS base

RUN groupadd --gid 2000 pbt-rpc \
    && useradd --uid 1000 --gid 2000 --create-home checker

FROM base AS candidate

FROM base AS checker

RUN pip install --no-cache-dir pytest==8.3.5 hypothesis==6.131.9

CMD ["tail", "-f", "/dev/null"]
