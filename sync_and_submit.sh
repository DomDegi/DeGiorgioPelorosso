#!/bin/bash
# Usage: ./sync_and_submit.sh <username>

USER=$1
REMOTE="login.g100.cineca.it" # Using internal node for direct access

echo "Syncing local files to Galileo100..."

# Sync scripts
scp job.sh submit.sh $USER@$REMOTE:~/

# Make sure a inputs folder exist on the cluster
ssh $USER@$REMOTE "mkdir -p ~/inputs/csv_input; mkdir -p ~/inputs/config"

# Sync inputs
scp -r inputs/ $USER@$REMOTE:~/
# Sync useful scripts (optional, if you have any)
scp -r scripts/*.sh $USER@$REMOTE:~/

# Remote trigger
echo "Triggering remote submission script..."
ssh $USER@$REMOTE "bash ~/submit.sh"
