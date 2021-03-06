#!/usr/bin/env bash

HOST='localhost'
PORT='8088'

if [ ! -f "server/data/db.sqlite3" ]; then
    echo "Yang-Explorer database is not initialized .. please run start.sh first !!"
    exit -1
fi

echo ""

if [ -f "v/bin/activate" ]; then
	echo "Activating virtualenv .."
	source v/bin/activate
fi

echo "Starting YangExplorer server .."
echo "Use http://$HOST:$PORT/static/YangExplorer.html"
echo ""

cd server
python manage.py runserver $HOST:$PORT
