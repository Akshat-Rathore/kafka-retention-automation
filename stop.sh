#!/usr/bin/env bash

set -e

DIR=$(readlink -f $0 | xargs dirname)

echo -e "\n Stopping Kafka Brokers..."

docker-compose -f "$DIR/multiple-broker-compose.yml" down --remove-orphans

docker-compose -f "$DIR/multiple-broker-compose.yml" ps

exit 0
