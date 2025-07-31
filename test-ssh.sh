#!/bin/bash

# Test SSH connection with your current key
echo "Testing SSH connection to production server..."

# Setup SSH key (simulate what GitHub Actions does)
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Test with your actual private key
echo "Using local private key..."
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30 -i ~/.ssh/id_rsa milestonehre@65.20.74.159 'echo "SSH connection successful! Current user: $(whoami), Time: $(date)"'

if [ $? -eq 0 ]; then
    echo "✅ SSH connection works with local key"
else
    echo "❌ SSH connection failed with local key"
fi
