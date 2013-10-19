#!/bin/bash
DOCKER_HOST=${DOCKER_HOST:-}
IPADDR=`ifconfig docker0 | awk '/inet addr/ {split ($2,A,":"); print A[2]}'`
if [ ! -z "$DOCKER_HOST" ] ; then
    DOCKER="docker -H $DOCKER_HOST"
else
    DOCKER="docker"
fi
ROOT=`pwd`
for IMG in amara-app amara-mysql amara-solr amara-memcached amara-rabbitmq
do
    echo "Checking image $IMG..."
    if [ "`docker images | awk '{ print $1; }' | grep $IMG`" = "" ] ; then
        echo "Building $IMG image..."
        # check for top level image
        if [ "$IMG" = "amara-app" ] ; then
            cd $ROOT && docker build -t $IMG .
        else
            cd $ROOT/.docker/$IMG && docker build -t $IMG .
        fi
    fi
done

SOLR=$($DOCKER run -i -t -d amara-solr)
SOLR_PORT=$($DOCKER port $SOLR 8983)
RABBITMQ=$($DOCKER run -i -t -d amara-rabbitmq)
RABBITMQ_PORT=$($DOCKER port $RABBITMQ 5672)

echo "Containers: Solr:$SOLR:$SOLR_PORT RabbitMQ:$RABBITMQ:$RABBITMQ_PORT"

# run tests
$DOCKER run -i -t -h unisubs.example.com -e SKIP_CODE_PULL=true -e TEST_IPADDR=$IPADDR -e TEST_BROKER_PORT=$RABBITMQ_PORT -e TEST_SOLR_PORT=$SOLR_PORT amara-app /usr/local/bin/test_app

sleep 5

for CNT in $SOLR $RABBITMQ
do
    $DOCKER kill $CNT
    $DOCKER rm $CNT
done
