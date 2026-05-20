FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY conductor ./conductor
COPY README.md ./

EXPOSE 8080

CMD ["python", "-m", "conductor.app"]
