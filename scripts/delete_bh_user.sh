#!/bin/bash
api_server=bhs.ezdr.net
echo "Please enter the username (email) you wish to delete"
read username
echo "Please enter the password"
read -s password
# Getting a token for the user
auth_body="{"\""username"\"": "\""$username"\"", "\""password"\"": "\""$password"\""}"
token_json=`curl -s $api_server/auth -X POST -d "$auth_body"`
token=`echo "$token_json" | jq '.token' | tr -d '"'`
if [ "$token" == "null" ]
    then echo "Error occured while authenticating"
    echo "$token_json"
    exit 1
fi
# Deleting the user using the authentication token
auth_header="Authorization: Bearer $token"
deleted=`curl -s $api_server/user -X DELETE -H "$auth_header"`

