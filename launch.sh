#!/bin/sh
cd "$(dirname "$0")"
if pip list | grep  boto; then
    echo "Boto installed";
else
    echo "Trying to install boto"
    pip install boto
fi

python launch.py

