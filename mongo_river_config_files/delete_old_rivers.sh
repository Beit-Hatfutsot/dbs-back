#!/bin/bash

index_name=bhp6
host_name=localhost

echo "If you need to re-initialize the rivers, delete them and their index"
echo
echo "Run these commands line by line!"
echo "Don't run the next line before ensuring that the previous command finished successfully."
echo "Check for  'Stopped river \$RIVER_NAME' in /var/log/elasticsearch/elasticsearch.log"
echo
echo

if [ "$1" != "" ];
    then host_name=$1
fi

echo "Delete the rivers:"

for i in `ls *.json`; do
    r_name=`echo $i | cut -d. -f1`
    r_full_name=${index_name}_${r_name}
    echo "curl -X DELETE $host_name:9200/_river/$r_full_name"
done

echo "Delete the index:"
echo "curl -X DELETE $host_name:9200/$index_name/"
echo "Check the rivers status at http://localhost:9200/_plugin/river-mongodb/"
