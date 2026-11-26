FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-web.lock ./requirements-web.lock
RUN pip install -r requirements-web.lock \
    && groupadd --gid 10001 consult \
    && useradd --uid 10001 --gid consult --no-create-home consult
COPY webapp ./webapp
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN DJANGO_SECRET_KEY=static-collection-build-only python webapp/manage.py collectstatic --noinput \
    && chmod 755 /app/entrypoint.sh
WORKDIR /app/webapp
USER 10001:10001
EXPOSE 8000
CMD ["/app/entrypoint.sh"]
