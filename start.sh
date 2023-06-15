#!/usr/bin/env bash

set -e

DIR=$(readlink -f $0 | xargs dirname)

echo -e "\nStarting Kafka Brokers..."

docker-compose -f $DIR/multiple-broker-compose.yml up -d

docker-compose -f $DIR/multiple-broker-compose.yml ps

echo -e "\n------------------------------------------------------------------------------------------------------"
echo -e "Grafana (Login : admin / Password : kafka) : http://localhost:3000"
echo -e "Prometheus : http://localhost:9090"
echo -e "\n------------------------------------------------------------------------------------------------------"

exit 0
