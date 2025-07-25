#!/bin/bash

# Manual Horilla Deployment Script
# Run this script locally to deploy to the server manually

set -e

REMOTE_HOST="65.20.74.159"
REMOTE_USER="milestonehre"
SSH_KEY="~/Downloads/a1"
APP_DIR="horilla-app"

echo "🚀 Starting manual Horilla deployment..."

# Function to run commands on remote server
ssh_exec() {
    ssh -i "$SSH_KEY" "$REMOTE_USER@$REMOTE_HOST" "$1"
}

# Step 1: Test connection
echo "📡 Testing SSH connection..."
if ! ssh_exec "echo 'Connection successful'"; then
    echo "❌ SSH connection failed!"
    exit 1
fi

# Step 2: Clean up any existing processes
echo "🛑 Stopping any existing Horilla processes..."
ssh_exec "pkill -f 'gunicorn.*horilla' || echo 'No existing processes found'"

# Step 3: Backup existing installation
echo "🔄 Backing up existing installation..."
ssh_exec "if [ -d '$APP_DIR' ]; then mv '$APP_DIR' '${APP_DIR}-backup-$(date +%Y%m%d-%H%M%S)' || true; fi"

# Step 4: Create fresh directory
echo "📁 Creating fresh application directory..."
ssh_exec "mkdir -p $APP_DIR"

# Step 5: Transfer files using rsync (more efficient than SCP for large transfers)
echo "📋 Transferring files to server..."
rsync -avz --delete -e "ssh -i $SSH_KEY" \
    --exclude='.git/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='node_modules/' \
    --exclude='.github/' \
    ./ "$REMOTE_USER@$REMOTE_HOST:$APP_DIR/"

# Step 6: Create production environment file
echo "🔧 Setting up production environment..."
ssh_exec "cd $APP_DIR && cat > .env << 'EOF'
DEBUG=False
SECRET_KEY=django-prod-$(openssl rand -hex 16)
ALLOWED_HOSTS=65.20.74.159,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://65.20.74.159:8002
TIME_ZONE=UTC
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=horilla_production.sqlite3
EOF"

# Step 7: Set up Python environment
echo "🐍 Setting up Python virtual environment..."
ssh_exec "cd $APP_DIR && python3 -m venv venv"

# Step 8: Install dependencies
echo "📦 Installing dependencies..."
ssh_exec "cd $APP_DIR && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"

# Step 9: Run migrations
echo "🗄️ Running database migrations..."
ssh_exec "cd $APP_DIR && source venv/bin/activate && python manage.py makemigrations && python manage.py migrate"

# Step 10: Collect static files
echo "📊 Collecting static files..."
ssh_exec "cd $APP_DIR && source venv/bin/activate && python manage.py collectstatic --noinput"

# Step 11: Create admin user
echo "👤 Creating admin user..."
ssh_exec "cd $APP_DIR && source venv/bin/activate && python manage.py createhorillauser --first_name admin --last_name admin --username admin --password admin --email admin@horilla.com --phone 1234567890 || echo 'Admin user already exists'"

# Step 12: Create startup script
echo "📄 Creating startup script..."
ssh_exec "cd $APP_DIR && cat > start.sh << 'EOF'
#!/bin/bash
cd \$(dirname \$0)
source venv/bin/activate

# Kill any existing instances
pkill -f 'gunicorn.*horilla' || true
sleep 2

# Start Horilla
echo 'Starting Horilla...'
nohup gunicorn --bind 0.0.0.0:8002 --workers 2 --timeout 60 horilla.wsgi:application > horilla.log 2>&1 &

echo 'Horilla started!'
echo 'Application should be accessible at http://65.20.74.159:8002'
echo 'Login: admin / admin'
EOF"

ssh_exec "cd $APP_DIR && chmod +x start.sh"

# Step 13: Create stop script
echo "🛑 Creating stop script..."
ssh_exec "cd $APP_DIR && cat > stop.sh << 'EOF'
#!/bin/bash
echo 'Stopping Horilla...'
pkill -f 'gunicorn.*horilla' || echo 'No Horilla process found'
echo 'Horilla stopped.'
EOF"

ssh_exec "cd $APP_DIR && chmod +x stop.sh"

# Step 14: Start the application
echo "▶️ Starting Horilla application..."
ssh_exec "cd $APP_DIR && ./start.sh"

# Step 15: Wait and verify
echo "⏳ Waiting for application to start..."
sleep 10

if ssh_exec "pgrep -f 'gunicorn.*horilla' > /dev/null"; then
    echo "✅ Horilla deployed and started successfully!"
    echo ""
    echo "🌐 Application URL: http://65.20.74.159:8002"
    echo "🔑 Login: admin / admin"
    echo ""
    echo "📊 Management commands:"
    echo "  Start:  ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_HOST 'cd $APP_DIR && ./start.sh'"
    echo "  Stop:   ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_HOST 'cd $APP_DIR && ./stop.sh'"
    echo "  Logs:   ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_HOST 'cd $APP_DIR && tail -f horilla.log'"
else
    echo "❌ Failed to start Horilla. Checking logs..."
    ssh_exec "cd $APP_DIR && tail -20 horilla.log 2>/dev/null || echo 'No log file found'"
    echo ""
    echo "🔍 To debug, connect to server and check:"
    echo "  ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_HOST"
    echo "  cd $APP_DIR"
    echo "  tail -f horilla.log"
fi
