######################################
### INTERMEDIATE PREPARATION STAGE ###
######################################

FROM amazonlinux:2 AS builder

WORKDIR /home/build

# Prepare ClamAV build environment
RUN yum update -y && \
yum install -y gcc glibc-devel gzip libicu-devel make openssl-devel readline-devel tar wget

ENV POSTGRESQL_VERSION=16.1

RUN wget -O - https://ftp.postgresql.org/pub/source/v$POSTGRESQL_VERSION/postgresql-$POSTGRESQL_VERSION.tar.gz | tar -xzf -

# Configure and build only pg_dump and pg_restore
RUN cd postgresql-$POSTGRESQL_VERSION && \
    ./configure --without-readline --without-zlib --with-openssl && \
    cd src/bin/pg_dump && \
    make pg_dump pg_restore && \
    cd ../../../..

# Extract required binaries and libraries for use in application container
RUN mkdir -p bin lib && \
    cp postgresql-$POSTGRESQL_VERSION/src/bin/pg_dump/pg_dump bin/. && \
    cp postgresql-$POSTGRESQL_VERSION/src/bin/pg_dump/pg_restore bin/. && \
    cp postgresql-$POSTGRESQL_VERSION/src/interfaces/libpq/libpq.so.5* lib/.

#######################################
### APPLICATION RUNTIME ENVIRONMENT ###
#######################################

FROM public.ecr.aws/lambda/python:3.11

RUN yum update -y && \
yum install -y aws-cli ca-certificates curl gzip tar yum-utils

# The Liquibase RPM repo currently serves unsigned packages (fails yum gpgcheck),
# so install the release tarball and verify its pinned checksum instead.
ENV LIQUIBASE_VERSION=4.27.0
ENV LIQUIBASE_SHA256=50d89e1fc10249bf198f1a8ff2d81fd0b68e6ca0805db28a94d38649784d82f0
RUN curl -fsSL -o /tmp/liquibase.tar.gz "https://github.com/liquibase/liquibase/releases/download/v${LIQUIBASE_VERSION}/liquibase-${LIQUIBASE_VERSION}.tar.gz" && \
    echo "${LIQUIBASE_SHA256}  /tmp/liquibase.tar.gz" | sha256sum -c - && \
    mkdir -p /opt/liquibase && \
    tar -xzf /tmp/liquibase.tar.gz -C /opt/liquibase && \
    ln -s /opt/liquibase/liquibase /usr/local/bin/liquibase && \
    rm -f /tmp/liquibase.tar.gz

RUN yum install -y java-17-amazon-corretto-headless && \
    yum clean all

ENV JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto
ENV JAVA_OPTS="-Xmx2g"
ENV PATH=$JAVA_HOME/bin:$PATH

# Copy pg_dump and pg_restore binaries from the builder container
COPY --from=builder /home/build/bin /usr/local/bin
COPY --from=builder /home/build/lib /usr/local/lib

ENV LD_LIBRARY_PATH="/usr/local/lib:$LD_LIBRARY_PATH"

# Copy application files
COPY files/src/*.py ${LAMBDA_TASK_ROOT}
COPY files/src/utils/*.py ${LAMBDA_TASK_ROOT}/utils/
COPY files/src/requirements.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN pip3 install --no-cache --upgrade pip setuptools && \
    pip3 install -Ur /${LAMBDA_TASK_ROOT}/requirements.txt && \
    pip3 install --platform manylinux2014_x86_64 --target=package --implementation cp --python-version 3.11 --only-binary=:all: --upgrade "psycopg[binary]" -t .

CMD ["app.lambda_handler"]

# checkov:skip=CKV_DOCKER_2:Not a long lived service, just for migrations, no need for health checks
# checkov:skip=CKV_DOCKER_3:No user needed