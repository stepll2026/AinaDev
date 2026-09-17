# PostgreSQL 16 + pgvector + zhparser（中文全文检索）
FROM pgvector/pgvector:pg16

# 安装 PGDG 源中的 zhparser（含 scws 依赖）
RUN apt-get update \
    && apt-get install -y --no-install-recommends wget ca-certificates gnupg \
    && echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-zhparser \
    && rm -rf /var/lib/apt/lists/*
