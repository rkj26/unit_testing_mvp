FROM python:3.11-slim

RUN pip install --no-cache-dir pytest hypothesis

CMD ["tail", "-f", "/dev/null"]
