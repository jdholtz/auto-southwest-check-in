#!/bin/sh

if [ ! -z ${SW_USERNAME+x} ] && [ ! -z ${SW_PASSWORD+x}  ]; then
  echo "Starting in account mode..."
  python3 southwest.py "$SW_USERNAME" "$SW_PASSWORD"
elif [ ! -z ${FIRST_NAME+x} ] && [ ! -z ${LAST_NAME+x} ] && [ ! -z ${CONFIRMATION_NUMBER+x} ]; then
  echo "Starting in reservation mode..."
  python3 southwest.py $CONFIRMATION_NUMBER $FIRST_NAME $LAST_NAME
else
  exit 1
fi

