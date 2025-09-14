#!/bin/bash

# Heroku Deployment Script for Voicebot
echo "🚀 Deploying Voicebot to Heroku..."

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Heroku CLI not found. Please install it first:"
    echo "   brew tap heroku/brew && brew install heroku"
    exit 1
fi

# Check if logged in to Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo "❌ Not logged in to Heroku. Please run: heroku login"
    exit 1
fi

# Get app name from user
read -p "Enter your Heroku app name (or press Enter for auto-generated): " APP_NAME

# Create Heroku app
if [ -z "$APP_NAME" ]; then
    echo "📱 Creating Heroku app with auto-generated name..."
    heroku create
else
    echo "📱 Creating Heroku app: $APP_NAME"
    heroku create $APP_NAME
fi

# Get the actual app name (in case it was auto-generated)
ACTUAL_APP_NAME=$(heroku apps:info --json | python3 -c "import sys, json; print(json.load(sys.stdin)['name'])" 2>/dev/null || echo "unknown")

# Set environment variables
echo "🔧 Setting up environment variables..."
echo "Please enter your Vapi credentials:"

read -p "VAPI_API_KEY: " VAPI_KEY
read -p "VAPI_ASSISTANT_ID: " ASSISTANT_ID

if [ -n "$VAPI_KEY" ] && [ -n "$ASSISTANT_ID" ]; then
    heroku config:set VAPI_API_KEY="$VAPI_KEY"
    heroku config:set VAPI_ASSISTANT_ID="$ASSISTANT_ID"
    echo "✅ Environment variables set"
else
    echo "⚠️  Environment variables not set. You can set them later with:"
    echo "   heroku config:set VAPI_API_KEY=your_key"
    echo "   heroku config:set VAPI_ASSISTANT_ID=your_id"
fi

# Prepare files for deployment
echo "📦 Preparing deployment files..."

# Use cloud-ready requirements
cp requirements_cloud.txt requirements.txt

# Initialize git if needed
if [ ! -d ".git" ]; then
    echo "📝 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit for Heroku deployment"
fi

# Add Heroku remote
echo "🔗 Adding Heroku remote..."
heroku git:remote -a $ACTUAL_APP_NAME

# Deploy
echo "🚀 Deploying to Heroku..."
git add .
git commit -m "Deploy to Heroku" || echo "No changes to commit"
git push heroku main

# Check deployment status
echo "🔍 Checking deployment status..."
heroku ps

# Show app info
echo ""
echo "🎉 Deployment complete!"
echo "📱 App Name: $ACTUAL_APP_NAME"
echo "🌐 URL: https://$ACTUAL_APP_NAME.herokuapp.com"
echo "📊 Health Check: https://$ACTUAL_APP_NAME.herokuapp.com/health"
echo "🎮 Demo: https://$ACTUAL_APP_NAME.herokuapp.com/demo"
echo "📚 API Docs: https://$ACTUAL_APP_NAME.herokuapp.com/docs"

# Open the app
read -p "Open the app in browser? (y/n): " OPEN_APP
if [ "$OPEN_APP" = "y" ] || [ "$OPEN_APP" = "Y" ]; then
    heroku open
fi

echo ""
echo "🔧 Useful commands:"
echo "   heroku logs --tail                 # View logs"
echo "   heroku config                      # View environment variables"
echo "   heroku ps:scale web=1              # Scale dynos"
echo "   heroku run bash                    # SSH into dyno"

echo ""
echo "✅ Deployment script completed!"
