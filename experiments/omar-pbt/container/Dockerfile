FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates docker-cli \
    && rm -rf /var/lib/apt/lists/*
RUN docker --version
COPY container/requirements.lock.txt /tmp/requirements.lock.txt
RUN pip install --no-cache-dir -r /tmp/requirements.lock.txt && pip check \
    && pip freeze > /opt/runner-dependencies.txt \
    && dpkg-query -W > /opt/runner-system-packages.txt
COPY snapshot/docker/bcb-pbt/requirements.txt /tmp/bcb-pbt-requirements.txt
RUN python -m venv /opt/bcb-venv \
    && /opt/bcb-venv/bin/python -m pip install --no-cache-dir --disable-pip-version-check \
        -r /tmp/bcb-pbt-requirements.txt \
    && /opt/bcb-venv/bin/python -m pip check
RUN /opt/bcb-venv/bin/python -m pip freeze > /opt/candidate-dependencies.txt
COPY snapshot/ /opt/archive/snapshot/
COPY PROVENANCE.json verify_snapshot.py /opt/archive/
# .env.example is a tracked source blob, not a credential; restore it explicitly for verification.
COPY snapshot/.env.example /opt/archive/snapshot/.env.example
RUN python /opt/archive/verify_snapshot.py
COPY container/pbt_runner/ /opt/runner/pbt_runner/
ENV PYTHONPATH=/opt/runner PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PBT_ARCHIVE=/opt/archive/snapshot IPYTHONDIR=/tmp/ipython
WORKDIR /opt/runner
LABEL org.opencontainers.image.title="BigCodeBench PBT reproduction runner" \
      org.opencontainers.image.source="https://github.com/rkj26/unit_testing_mvp" \
      org.opencontainers.image.description="Cached analysis and explicitly gated fresh fixed-input PBT replication" \
      org.omar-pbt.candidate-python="/opt/bcb-venv/bin/python"
ENTRYPOINT ["python", "-m", "pbt_runner"]
CMD ["--help"]
