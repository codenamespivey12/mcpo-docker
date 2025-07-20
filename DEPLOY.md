# 🚀 Railway Deployment Guide

This guide will help you deploy your MCP Docker Proxy to Railway in just a few minutes.

## Prerequisites

- GitHub account
- Railway account (free to sign up)
- Your API keys ready (E2B_API_KEY, EXA_API_KEY)

## Step-by-Step Deployment

### 1. Push Your Code to GitHub

```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit - MCP Docker Proxy"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

### 2. Deploy to Railway

1. **Go to [Railway.app](https://railway.app)** and sign up/login
2. **Click "New Project"**
3. **Select "Deploy from GitHub repo"**
4. **Choose your MCP Docker Proxy repository**
5. **Railway will automatically detect the Dockerfile and start building**

### 3. Configure Environment Variables

In your Railway project dashboard:

1. **Go to the "Variables" tab**
2. **Add these environment variables:**

```bash
# Required for API-based servers (set to "false" to enable)
E2B_DISABLED=true
EXA_DISABLED=true

# Optional: Add API keys if you want to enable these servers
E2B_API_KEY=your_e2b_api_key_here
EXA_API_KEY=your_exa_api_key_here

# Optional: Customize settings
TIMEZONE=America/New_York
LOG_LEVEL=info
LOG_FORMAT=json
```

### 4. Test Your Deployment

Once deployed, Railway will give you a URL like `https://your-app-name.railway.app`

Test your endpoints:

```bash
# Replace YOUR_APP_URL with your actual Railway URL
export APP_URL="https://your-app-name.railway.app"

# Test server info
curl $APP_URL/

# Test server status
curl $APP_URL/status

# Test memory server
curl $APP_URL/memory

# Test a tool call
curl -X POST $APP_URL/memory \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "create_entities",
    "arguments": {
      "entities": [
        {
          "name": "Test_Entity",
          "entityType": "test",
          "observations": ["Created via Railway deployment"]
        }
      ]
    }
  }'
```

## 🎯 What's Included by Default

Your Railway deployment includes these MCP servers:

### ✅ **Always Available (No API Keys Required)**
- **Memory Server** - Knowledge graph storage (`/memory`)
- **Time Server** - Date/time operations (`/time`)
- **Sequential Thinking** - Structured reasoning (`/sequential-thinking`)
- **Context7** - Library documentation (`/context7`)

### 🔑 **API Key Required (Disabled by Default)**
- **E2B Server** - Code execution (`/e2b`)
- **Exa Server** - Web search (`/exa`)

## 🔧 Enabling API-Based Servers

To enable E2B or Exa servers:

1. **Get your API keys:**
   - E2B: https://e2b.dev
   - Exa: https://exa.ai

2. **In Railway Variables tab, add:**
   ```bash
   E2B_API_KEY=your_actual_key
   E2B_DISABLED=false
   
   EXA_API_KEY=your_actual_key
   EXA_DISABLED=false
   ```

3. **Redeploy** (Railway will auto-redeploy when you change variables)

## 📊 Railway Pricing

- **Hobby Plan**: $5/month
- **Pay-per-use**: Only pay for what you consume
- **Free trial**: $5 credit to get started

## 🔍 Monitoring Your App

In Railway dashboard you can:
- **View logs** - See real-time application logs
- **Monitor metrics** - CPU, memory, network usage
- **Check deployments** - See build and deploy history
- **Manage domains** - Add custom domains

## 🛠 Troubleshooting

### Build Fails
- Check the "Deployments" tab for build logs
- Ensure all files are committed to GitHub
- Verify Dockerfile syntax

### App Won't Start
- Check "Logs" tab for startup errors
- Verify environment variables are set correctly
- Check that PORT environment variable is being used

### Tools Not Working
- Verify API keys are correct and not expired
- Check that servers are not disabled
- Review application logs for specific errors

### Memory Issues
- Railway provides 512MB RAM by default
- Monitor usage in the Metrics tab
- Consider upgrading plan if needed

## 🚀 Next Steps

Once deployed, you can:

1. **Add custom domain** in Railway settings
2. **Set up monitoring** with Railway's built-in tools
3. **Scale resources** if needed
4. **Add more MCP servers** by updating the config

## 📝 Configuration Updates

To add new MCP servers or modify settings:

1. **Update `config.production.json`**
2. **Commit and push to GitHub**
3. **Railway auto-deploys** the changes

## 🆘 Need Help?

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **Project Issues**: Create an issue in your GitHub repo

---

🎉 **Congratulations!** Your MCP Docker Proxy is now running on Railway and accessible worldwide!