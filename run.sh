#!/bin/bash
if [ -z "$VCAP_APP_PORT" ];
   then SERVER_PORT=80;
   else SERVER_PORT="$VCAP_APP_PORT";
fi

echo "intalacaio"
 
python java_install.py