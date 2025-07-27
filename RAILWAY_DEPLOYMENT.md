# Railway Deployment Guide for Church Map Project

## 🚀 Quick Deployment Steps

### 1. Push to GitHub
```bash
git add .
git commit -m "Ready for Railway deployment"
git push origin main
```

### 2. Deploy on Railway
1. Go to [railway.app](https://railway.app)
2. Sign up/login with GitHub
3. Click "Deploy from GitHub repo"
4. Select your church-map repository
5. Railway will auto-detect Django and deploy!

### 3. Configure Environment Variables
In Railway dashboard, add these environment variables:

**Required:**
```
DJANGO_SETTINGS_MODULE=church_map_project.settings_railway
SECRET_KEY=your-super-secret-key-here
DEBUG=False
```

**Optional:**
```
OPENROUTESERVICE_API_KEY=your-api-key-here
```

### 4. Add Database (Optional)
- Railway can provide PostgreSQL database
- Click "Add Plugin" → "PostgreSQL"
- Railway will automatically set DATABASE_URL

## 🔧 Configuration Files Created

- **`Procfile`** - Tells Railway how to run your app
- **`railway.json`** - Railway-specific configuration
- **`runtime.txt`** - Specifies Python version
- **`settings_railway.py`** - Railway-optimized Django settings
- **`.gitignore`** - Excludes unnecessary files from deployment

## 📊 Expected Costs

Your Church Map app will use approximately:
- **$2-3/month** of the $5 Railway credit
- **Very low resource usage** due to efficient architecture
- **Free PostgreSQL database** (if you choose to use it)

## 🔍 Deployment Features

✅ **Automatic HTTPS** - Railway provides SSL certificates  
✅ **Custom domains** - Add your own domain easily  
✅ **Auto-deployments** - Deploys on every git push  
✅ **Environment variables** - Secure configuration management  
✅ **Database integration** - Optional PostgreSQL database  
✅ **Static file serving** - WhiteNoise handles static files  
✅ **Logging** - View logs in Railway dashboard  

## 🛠️ Post-Deployment Steps

### 1. Run Initial Setup
Railway will automatically run:
```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 2. Create Superuser (Optional)
In Railway dashboard terminal:
```bash
python manage.py createsuperuser
```

### 3. Import Church Data
If you have church data to import:
```bash
python manage.py shell
# Run your import scripts
```

## 🔧 Troubleshooting

### Common Issues:

**1. Static Files Not Loading**
- Check that `whitenoise` is in requirements.txt
- Verify `STATICFILES_STORAGE` setting in settings_railway.py

**2. Database Connection Issues**
- Ensure `dj-database-url` is in requirements.txt
- Check DATABASE_URL environment variable

**3. Secret Key Errors**
- Set SECRET_KEY environment variable in Railway dashboard
- Use a strong, unique secret key

**4. ALLOWED_HOSTS Errors**
- Railway domains are automatically added to ALLOWED_HOSTS
- Add custom domain if you're using one

### Viewing Logs:
- Go to Railway dashboard
- Click on your project
- View "Deployments" tab for build logs
- View "Metrics" tab for runtime logs

## 🌐 Custom Domain Setup

1. **In Railway Dashboard:**
   - Go to Settings → Domains
   - Add your custom domain

2. **In Your DNS Provider:**
   - Add CNAME record pointing to Railway URL
   - Or A record pointing to Railway IP

3. **Update Settings:**
   - Add domain to ALLOWED_HOSTS (automatically handled)

## 📈 Monitoring

Railway provides built-in monitoring:
- **CPU usage**
- **Memory usage**
- **Request metrics**
- **Error tracking**
- **Deployment history**

## 🔄 Updates and Maintenance

**Automatic Deployments:**
- Push to GitHub → Railway auto-deploys
- Zero-downtime deployments
- Rollback capability

**Manual Commands:**
Use Railway dashboard terminal for:
- Database migrations
- Creating superusers
- Running management commands
- Debugging

## 💡 Tips for Success

1. **Keep it Simple:** Your current architecture is perfect for Railway
2. **Monitor Usage:** Check Railway dashboard for resource usage
3. **Use Environment Variables:** Never hardcode secrets
4. **Test Locally:** Use `python manage.py runserver` before deploying
5. **Check Logs:** Railway dashboard shows detailed deployment logs

## 🎉 You're Ready!

Your Church Map project is now fully configured for Railway deployment. The setup includes:

- ✅ Production-ready Django settings
- ✅ Static file handling with WhiteNoise
- ✅ Database configuration (SQLite + PostgreSQL support)
- ✅ Security settings for HTTPS
- ✅ Logging and monitoring
- ✅ Automatic deployments

Just push to GitHub and deploy on Railway!