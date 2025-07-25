# Horilla Automated Deployment

> **Status**: Automated deployment is now active! 🚀

This repository includes automated deployment workflows using GitHub Actions to deploy Horilla HR software to your server.

## 🚀 Deployment Options

### 1. Shared Hosting Deployment (Default)
- Uses Python virtual environment
- SQLite database for simplicity
- No Docker required
- Suitable for shared hosting environments

### 2. Docker Deployment
- Full containerized deployment
- PostgreSQL database
- Requires Docker on the target server

## 📋 Setup Instructions

### 1. Fork the Repository
This repository is already forked from the original Horilla repository.

### 2. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and Variables → Actions, and add the following secrets:

#### Required Secrets:
- `SSH_PRIVATE_KEY`: Your SSH private key for server access
- `HOST`: Server IP address (default: 65.20.74.159)
- `USERNAME`: SSH username (default: milestonehre)

#### Optional Secrets:
- `DJANGO_SECRET_KEY`: Django secret key (auto-generated if not provided)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `CSRF_TRUSTED_ORIGINS`: Comma-separated list of trusted origins
- `PORT`: SSH port (default: 22)

### 3. SSH Key Setup

1. Generate an SSH key pair (if you don't have one):
   ```bash
   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
   ```

2. Add the public key to your server's `~/.ssh/authorized_keys`

3. Add the private key content to the `SSH_PRIVATE_KEY` GitHub secret

## 🔧 How to Deploy

### Method 1: Automatic Deployment (Push to main)
- Push any changes to the `main` or `master` branch
- The workflow will automatically run tests and deploy

### Method 2: Manual Deployment
1. Go to your GitHub repository → Actions → "Deploy to Server"
2. Click "Run workflow"
3. Choose deployment type:
   - `shared-hosting`: For traditional hosting environments
   - `docker`: For Docker-based deployment
4. Optionally check "Force deployment" to skip tests

## 📁 What Gets Deployed

### Shared Hosting Deployment:
- Python virtual environment setup
- SQLite database with migrations
- Static files collection
- Gunicorn WSGI server
- Start/stop scripts
- Auto-generated admin user (admin/admin)

### Docker Deployment:
- PostgreSQL database container
- Django application container
- Docker Compose orchestration
- Health checks and auto-restart

## 🌐 Accessing Your Application

After successful deployment:
- **URL**: http://65.20.74.159:8002
- **Username**: admin
- **Password**: admin

## 📊 Managing Your Deployment

### Shared Hosting Commands:
```bash
# Connect to your server
ssh -i ~/Downloads/a1 milestonehre@65.20.74.159

# Navigate to the application
cd ~/horilla-app

# Start the application
./start_horilla.sh

# Stop the application
./stop_horilla.sh

# View logs
tail -f horilla.log

# Restart the application
./stop_horilla.sh && ./start_horilla.sh
```

### Docker Commands:
```bash
# Connect to your server
ssh -i ~/Downloads/a1 milestonehre@65.20.74.159

# Navigate to the application
cd ~/horilla-docker-deployment

# View running containers
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Restart services
docker compose -f docker-compose.prod.yml restart

# Stop services
docker compose -f docker-compose.prod.yml down

# Start services
docker compose -f docker-compose.prod.yml up -d
```

## 🔄 Updating Your Deployment

1. Make changes to your code
2. Commit and push to the `main` branch
3. The GitHub Action will automatically:
   - Run tests
   - Create a backup of the existing deployment
   - Deploy the new version
   - Start the application

## 🛠️ Troubleshooting

### Common Issues:

1. **SSH Connection Failed**
   - Verify your SSH key is correct
   - Check if the server IP and username are correct
   - Ensure the SSH key has proper permissions (600)

2. **Deployment Failed**
   - Check the GitHub Actions logs
   - Verify server has enough disk space
   - Check if Python 3 is available on the server

3. **Application Won't Start**
   - SSH into the server and check logs
   - Verify all dependencies are installed
   - Check if port 8002 is available

4. **Database Issues**
   - For shared hosting: Check if SQLite file permissions are correct
   - For Docker: Verify PostgreSQL container is healthy

### Debug Commands:
```bash
# Check if Horilla is running
pgrep -f "gunicorn.*horilla"

# Check port availability
netstat -tlnp | grep :8002

# Check disk space
df -h

# Check Python version
python3 --version
```

## 🔐 Security Considerations

1. **Change Default Password**: After first login, change the admin password
2. **Environment Variables**: Use GitHub secrets for sensitive data
3. **SSL/HTTPS**: Consider setting up SSL certificates for production
4. **Firewall**: Configure firewall rules to restrict access
5. **Regular Updates**: Keep the application and dependencies updated

## 📝 Customization

### Modifying Deployment Scripts:
- Edit `.github/workflows/deploy-to-server.yml` for workflow changes
- Modify the embedded deployment scripts for custom setup requirements

### Adding New Environments:
1. Create new workflow files for different environments
2. Add environment-specific secrets
3. Modify deployment scripts accordingly

## 🆘 Support

If you encounter issues:
1. Check the GitHub Actions logs
2. Review server logs
3. Consult the original Horilla documentation
4. Create an issue in this repository
