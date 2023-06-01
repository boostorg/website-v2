#!/bin/sh

# Wait for the other container to be ready
while ! nc -z web 8000; do
  sleep 1
done
