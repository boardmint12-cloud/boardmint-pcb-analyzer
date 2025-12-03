# 🚀 **Deploy to Vercel - Frontend + Backend (All-in-One)**

## ✅ **Setup Complete!**

Your project is now configured for **full-stack Vercel deployment**:
- ✅ Frontend (React + Vite)
- ✅ Backend (FastAPI serverless functions)
- ✅ Single domain deployment

---

## 📦 **What Was Configured:**

### **1. Created Files:**
- `api/index.py` - Serverless function entry point
- `requirements.txt` - Python dependencies for Vercel
- `vercel.json` - Deployment configuration

### **2. Route Structure:**
```
https://boardmint.io/          → Frontend (React)
https://boardmint.io/api/*     → Backend API (FastAPI)
```

**Same domain for everything!** No CORS issues! 🎉

---

## 🚀 **Deploy to Vercel (10 minutes)**

### **Step 1: Push to GitHub**

```bash
cd "/Users/pranavchahal/Documents/pcb - 1st intro"
git add .
git commit -m "feat: configure for Vercel full-stack deployment"
git push origin main
```

---

### **Step 2: Deploy to Vercel**

**Go to:** https://vercel.com/new

1. **Import Repository:**
   - Click "Import Git Repository"
   - Select: `boardmint12-cloud/boardmint-pcb-analyzer`
   - Click "Import"

2. **Project Settings:**
   ```
   Framework Preset: Other
   Root Directory: ./
   Build Command: (leave default)
   Output Directory: (leave default)
   Install Command: (leave default)
   ```

3. **Add Environment Variables:**
   
   Click "Environment Variables" and add these:
   
   ```bash
   # Supabase
   SUPABASE_URL=https://cbnrmppejmzwzpjuhoyc.supabase.co
   SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNibnJtcHBlam16d3pwanVob3ljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ2NjI0MzEsImV4cCI6MjA4MDIzODQzMX0.i1y_eua8LQWXTYPjsfceWV1XkEf2S49c_S-DnuKunhs
   SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNibnJtcHBlam16d3pwanVob3ljIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NDY2MjQzMSwiZXhwIjoyMDgwMjM4NDMxfQ.z5p-sFT0T9pN93eePkWa8V50pDy8Vwpzj-5rCDcG_9E
   SUPABASE_JWT_SECRET=ESTsszMwxIK3OA1cEe0pTcUc4HfTlxFdWxlsC/PLZwNQyqoCd8z08AKVxbBEWo+ZwIrY1TmMSR90wgcP1bKDjg==
   
   # Database
   DATABASE_URL=postgresql://postgres:1223pranavA@@db.cbnrmppejmzwzpjuhoyc.supabase.co:5432/postgres
   
   # Backend Config
   PYTHON_ENV=production
   BACKEND_HOST=0.0.0.0
   BACKEND_PORT=3000
   
   # Frontend (Vite variables - must start with VITE_)
   VITE_SUPABASE_URL=https://cbnrmppejmzwzpjuhoyc.supabase.co
   VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNibnJtcHBlam16d3pwanVob3ljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ2NjI0MzEsImV4cCI6MjA4MDIzODQzMX0.i1y_eua8LQWXTYPjsfceWV1XkEf2S49c_S-DnuKunhs
   VITE_API_URL=/api
   
   # CORS (your domain after setup)
   CORS_ORIGINS=https://boardmint.io,https://www.boardmint.io
   FRONTEND_URL=https://boardmint.io
   
   # OpenAI (if using AI features)
   OPENAI_API_KEY=your_openai_key_here
   ```
   
   **⚠️ Note:** `VITE_API_URL=/api` means API calls go to the same domain!

4. **Deploy:**
   - Click "Deploy"
   - Wait 3-5 minutes for build
   - You'll get a URL like: `boardmint-pcb-analyzer.vercel.app`

---

### **Step 3: Test Deployment**

**Test API:**
```bash
curl https://your-deployment.vercel.app/api/
# Should return: {"status":"healthy","service":"PCB Analyzer API"}
```

**Test Frontend:**
```bash
# Open in browser:
https://your-deployment.vercel.app/
# Should show homepage

# Test quote page:
https://your-deployment.vercel.app/quote
```

---

### **Step 4: Connect Domain (boardmint.io)**

**In Vercel Dashboard:**

1. Go to project **Settings → Domains**
2. Click "Add Domain"
3. Enter: `boardmint.io`
4. Also add: `www.boardmint.io`

**In Your Domain Registrar:**

Add these DNS records:

```
Type: A
Name: @
Value: 76.76.21.21
TTL: Auto

Type: CNAME
Name: www
Value: cname.vercel-dns.com
TTL: Auto
```

**Wait:** 5-30 minutes for DNS propagation

**Result:** Your site will be live at `https://boardmint.io`! 🎉

---

### **Step 5: Update Environment Variables for Production Domain**

After domain is connected, update these in Vercel:

```bash
CORS_ORIGINS=https://boardmint.io,https://www.boardmint.io
FRONTEND_URL=https://boardmint.io
```

Then redeploy (Deployments → Redeploy).

---

## 🔐 **Step 6: Security (CRITICAL!)**

### **⚠️ ROTATE SUPABASE KEYS IMMEDIATELY**

After deployment, your keys are live. You MUST rotate them:

1. **Go to Supabase Dashboard:**
   - https://supabase.com/dashboard
   - Select your project

2. **Rotate Keys:**
   - Settings → API → **"Reset anon key"** → Copy new key
   - Settings → API → **"Reset service_role key"** → Copy new key
   - Settings → Database → **"Reset database password"** → Copy new password

3. **Update Vercel Environment Variables:**
   - Settings → Environment Variables
   - Update all Supabase keys and DATABASE_URL
   - Update both `SUPABASE_ANON_KEY` and `VITE_SUPABASE_ANON_KEY`

4. **Redeploy:**
   - Deployments → Click "Redeploy"

5. **Update Supabase Auth URLs:**
   - In Supabase: Authentication → URL Configuration
   - Site URL: `https://boardmint.io`
   - Redirect URLs: `https://boardmint.io/**`

---

## 📊 **API Endpoints**

All API endpoints are available at `/api/*`:

```
GET  /api/                     → Health check
POST /api/quotes               → Submit quote
POST /api/auth/login           → Login
POST /api/auth/signup          → Signup
GET  /api/projects             → Get projects
POST /api/projects             → Create project
GET  /api/analyses/:id         → Get analysis
```

**Frontend Usage:**
```typescript
// No need for full URL - use relative paths!
const response = await fetch('/api/quotes', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(quoteData)
});
```

Already configured in your code since `VITE_API_URL=/api`! ✅

---

## ⚡ **Serverless Limitations**

**Vercel Serverless:**
- ⏱️ **Timeout:** 10 seconds (Hobby) / 60 seconds (Pro)
- 💾 **Memory:** 1024MB (Hobby) / 3008MB (Pro)
- 📦 **Max Size:** 50MB per function
- 🚀 **Cold Start:** ~1-3 seconds first request

**What Works Well:**
- ✅ Quote submissions
- ✅ Authentication
- ✅ Database queries
- ✅ Small file uploads
- ✅ Simple API calls

**What Might Timeout:**
- ⚠️ Large PCB file processing (>10s)
- ⚠️ Complex DRC analysis
- ⚠️ AI analysis of big files

**Solution:** For heavy processing, use:
- Background jobs (Supabase Functions)
- Or upgrade to Vercel Pro ($20/month = 60s timeout)
- Or move heavy processing to separate service later

---

## ✅ **Deployment Checklist**

- [ ] Push code to GitHub
- [ ] Deploy to Vercel
- [ ] Add all environment variables
- [ ] Test API endpoint (`/api/`)
- [ ] Test frontend homepage
- [ ] Test quote submission
- [ ] Connect boardmint.io domain
- [ ] Update DNS records
- [ ] Wait for DNS propagation
- [ ] Update CORS_ORIGINS
- [ ] **Rotate all Supabase keys**
- [ ] Update environment variables
- [ ] Redeploy
- [ ] Test with custom domain
- [ ] Test authentication
- [ ] Monitor logs for 24 hours

---

## 🎯 **Testing Your Deployment**

### **1. Test API Health:**
```bash
curl https://boardmint.io/api/
```
Expected:
```json
{
  "status": "healthy",
  "service": "PCB Analyzer API",
  "version": "1.0.0"
}
```

### **2. Test Quote Submission:**
Go to: `https://boardmint.io/quote`
- Fill out form
- Submit
- Check Supabase → quotes table

### **3. Test Authentication:**
Go to: `https://boardmint.io/login`
- Login with: `chahalpranav2312@gmail.com`
- Should redirect to projects

### **4. Check Logs:**
In Vercel Dashboard:
- Go to your project
- Click "Logs" tab
- Monitor for errors

---

## 💰 **Pricing**

| Plan | Price | Limits |
|------|-------|--------|
| **Hobby** | **FREE** | 100GB bandwidth, 10s timeout |
| **Pro** | **$20/month** | 1TB bandwidth, 60s timeout |

**Recommendation:** Start with Hobby, upgrade if you hit limits.

---

## 🆘 **Troubleshooting**

### **API Returns 404:**
- Check vercel.json routes configuration
- Verify api/index.py exists
- Check deployment logs

### **Build Fails:**
- Check Python version (3.9 specified)
- Verify requirements.txt is in root
- Check build logs in Vercel

### **CORS Errors:**
- Update CORS_ORIGINS environment variable
- Include your domain
- Redeploy after changing

### **Timeout Errors:**
- Heavy processing may timeout on Hobby plan
- Upgrade to Pro for 60s timeout
- Or optimize code / use background jobs

### **Environment Variables Not Working:**
- Frontend vars MUST start with `VITE_`
- After changing, must redeploy
- Check they're set for "Production" environment

---

## 🎉 **Success!**

**Your full-stack app is now deployed on Vercel!**

**URLs:**
- 🌐 Frontend: `https://boardmint.io`
- 🔌 API: `https://boardmint.io/api/`
- 📊 Dashboard: Vercel dashboard for monitoring

**All on one platform, one domain, zero configuration!** 🚀

---

## 📞 **Next Steps**

1. ✅ Deploy to Vercel (10 min)
2. ✅ Connect domain (5 min + DNS wait)
3. ⚠️ **Rotate Supabase keys** (5 min) - CRITICAL!
4. ✅ Test everything (10 min)
5. 🎉 You're live!

**Total time: ~30-45 minutes**

---

**Questions?** Just start with Step 1 - push to GitHub!
