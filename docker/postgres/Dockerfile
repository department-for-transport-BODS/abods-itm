#checkov:skip=CKV_DOCKER_9: ensure that apt isn't used
FROM postgres:15

# pg_cron (https://github.com/citusdata/pg_cron/tags)
ENV PG_CRON_VERSION=1.6.2
ENV PG_VERSION=15
ENV PG_CONF_SRC=/usr/share/postgresql/postgresql.conf.sample
ENV PG_CONF_DST=/etc/postgresql/postgresql.conf

# Install pg_cron.
RUN apt update \
    && apt install -y --no-install-recommends \
        ca-certificates libarchive-tools openssl tar wget \
    && wget -O pg_cron.tar.gz "https://github.com/citusdata/pg_cron/archive/v$PG_CRON_VERSION.tar.gz" \
    && mkdir -p /usr/src/pg_cron \
    && tar \
        --extract \
        --file pg_cron.tar.gz \
        --directory /usr/src/pg_cron \
        --strip-components 1 \
    && rm pg_cron.tar.gz \
    && apt install -y --no-install-recommends \
        autoconf \
        automake \
        g++ \
        clang-15 \
        libtool \
        libxml2-dev \
        make \
        perl \
        postgresql-server-dev-$PG_VERSION \
    && cd /usr/src/pg_cron \
    && make \
    && make NO_BGW=1 install \
    && rm -rf /usr/src/pg_cron

RUN sed "s/#shared_preload_libraries.*/shared_preload_libraries = 'pg_cron'/" \
    $PG_CONF_SRC > $PG_CONF_DST \
    && echo "cron.database_name = 'abods'" >> $PG_CONF_DST \

# checkov:skip=CKV_DOCKER_2:Not a long lived service, just for local dev, no need for health checks
# checkov:skip=CKV_DOCKER_3:No user needed