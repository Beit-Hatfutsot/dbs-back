#!/usr/bin/env bash

pip install -r requirements.txt
pip install -r requirements.migrate.txt
pip install pymssql==2.1.3

which java
java -version

# environment variables you might want to change
ELASTICSEARCH_DIR=${ELASTICSEARCH_DIR:="${HOME}/el"}
ELASTICSEARCH_WAIT_TIME=${ELASTICSEARCH_WAIT_TIME:="30"}
ELASTICSEARCH_CACHE_DIR=${ELASTICSEARCH_CACHE_DIR:="${HOME}/cache"}

# constants
ELASTICSEARCH_VERSION="5.2.2"
ELASTICSEARCH_PORT="9200"

ELASTICSEARCH_DL_URL="https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-${ELASTICSEARCH_VERSION}.tar.gz"
CACHED_DOWNLOAD="${ELASTICSEARCH_CACHE_DIR}/elasticsearch-${ELASTICSEARCH_VERSION}.tar.gz"
mkdir -p "${ELASTICSEARCH_CACHE_DIR}"
if [ -d "${ELASTICSEARCH_DIR}" ]; then
    rm -rf "${ELASTICSEARCH_DIR}"
fi
mkdir -p "${ELASTICSEARCH_DIR}"

wget --continue --output-document "${CACHED_DOWNLOAD}" "${ELASTICSEARCH_DL_URL}"
tar -xaf "${CACHED_DOWNLOAD}" --strip-components=1 --directory "${ELASTICSEARCH_DIR}"

echo "http.port: ${ELASTICSEARCH_PORT}" >> ${ELASTICSEARCH_DIR}/config/elasticsearch.yml

# Make sure to use the exact parameters you want for ElasticSearch and give it enough sleep time to properly start up
nohup bash -c "${ELASTICSEARCH_DIR}/bin/elasticsearch 2>&1" &

echo "Started elasticsearch, to kill run 'sudo pkill -fe -9 elasticsearch'"

sleep "${ELASTICSEARCH_WAIT_TIME}"
