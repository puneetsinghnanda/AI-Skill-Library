# truminds/pg-backup (OPS-01 §5.1, §9): postgres:16 plus pgBackRest.
# Used twice in compose.prod.yml: as the database server (so archive_command can push WAL) and as the
# `backup` service (scheduled full and differential backups). Built with the insights release:
#   docker build -t truminds/pg-backup:X.Y.Z deploy/images/pg-backup
# The release pipeline pins POSTGRES_IMAGE by digest (OPS-03 §3). No secret is baked in: the cipher key
# and storage credentials are Docker secrets read at run time by `pgbr`.
ARG POSTGRES_IMAGE=postgres:16
FROM ${POSTGRES_IMAGE}

ARG VERSION=0.0.0
ARG REVISION=unknown
LABEL org.opencontainers.image.title="truminds/pg-backup" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends pgbackrest ca-certificates; \
    rm -rf /var/lib/apt/lists/*; \
    install -d -o postgres -g postgres -m 0750 /var/log/pgbackrest /var/spool/pgbackrest /etc/pgbackrest

COPY pgbackrest.conf /etc/pgbackrest/pgbackrest.conf
COPY pgbr pg-backup-entry /usr/local/bin/
RUN chmod 0755 /usr/local/bin/pgbr /usr/local/bin/pg-backup-entry

ENTRYPOINT ["pg-backup-entry"]
# Default: behave exactly like the upstream postgres image.
CMD ["postgres"]
