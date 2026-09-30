# The digest is the repository's existing Python 3.12 slim execution image.
# Building this image installs dependencies; candidate execution remains
# network-disabled at runtime.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

ENV MPLBACKEND=Agg \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt /tmp/bcb-pbt-requirements.txt
RUN python -m pip install --no-cache-dir --disable-pip-version-check \
    -r /tmp/bcb-pbt-requirements.txt

WORKDIR /workspace
