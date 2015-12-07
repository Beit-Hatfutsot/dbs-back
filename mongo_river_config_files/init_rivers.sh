#!/bin/bash

index_name=bhp6
host_name=localhost

# Show how to initialize all the rivers specified in the jsons
echo "Run these commands line by line!"
echo
echo "Don't run the next line before ensuring that the previous river is running."
echo "Check for 'setRiverStatus called with RIVER_NAME - RUNNING' in /var/log/elasticsearch/elasticsearch.log"
echo

if [ "$1" != "" ];
    then host_name=$1
    if [ "$2" != "" ];
        then index_name=$2
    fi
fi


for i in `ls *.json`; do
    r_name=`echo $i | cut -d. -f1`
    r_full_name=${index_name}_${r_name}
    echo "curl -X PUT http://$host_name:9200/_river/$r_full_name/_meta -d @$i"
done
echo
echo "Check the rivers status at http://$host_name:9200/_plugin/river-mongodb/"
