#!/usr/bin/env bash
# Render build script
set -o errexit

pip install -r requirements.txt

# Run database migrations
flask db upgrade

# Seed initial data (admin user, sample school, etc.)
python seed.py
