# Simulated robot container (docker compose --profile sim up). Not used on the real Pi.
FROM python:3.11-slim
WORKDIR /edge
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
COPY requirements-video.txt .
RUN pip install -r requirements.txt -r requirements-video.txt
COPY . .
CMD ["python", "-m", "robot.main", "--sim"]
