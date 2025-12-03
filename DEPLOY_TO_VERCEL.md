# 🚀 **Deploy BoardMint to Vercel + boardmint.io**

## ✅ **Step 1: Code Pushed to GitHub** ✅

**Repository:** https://github.com/boardmint12-cloud/boardmint-pcb-analyzer

---

## 🌐 **Step 2: Deploy Frontend to Vercel (5 minutes)**

### **Option A: Deploy via Vercel Dashboard (Recommended)**

1. **Go to Vercel:**
   - Visit: https://vercel.com
   - Click **"Add New..."** → **"Project"**

2. **Connect GitHub:**
   - Click **"Continue with GitHub"**
   - Authorize Vercel to access your repositories
   - Select: **`boardmint12-cloud/boardmint-pcb-analyzer`**

3. **Configure Project:**
   ```
   Framework Preset: Vite
   Root Directory: frontend
   Build Command: npm run build
   Output Directory: dist
   Install Command: npm install
   ```

4. **Add Environment Variables:**
   Click "Environment Variables" and add:
   ```
   VITE_SUPABASE_URL=https://cbnrmppejmzwzpjuhoyc.supabase.co
   VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNibnJtcHBlam16d3pwanVob3ljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ2NjI0MzEsImV4cCI6MjA4MDIzODQzMX0.i1y_eua8LQWXTYPjsfceWV1XkEf2S49c_S-DnuKunhs
   VITE_API_URL=https://your-backend-url.com
   ```
   
   **⚠️ IMPORTANT:** You'll need to update `VITE_API_URL` after deploying the backend!

5. **Deploy:**
   - Click **"Deploy"**
   - Wait 2-3 minutes for build to complete
   - You'll get a URL like: `https://boardmint-pcb-analyzer.vercel.app`

---

### **Option B: Deploy via Vercel CLI**

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
cd "/Users/pranavchahal/Documents/pcb - 1st intro/frontend"
vercel

# Follow prompts:
# - Link to existing project? No
# - Project name: boardmint-pcb-analyzer
# - Which directory is your code in? ./
# - Want to override settings? Yes
#   - Build Command: npm run build
#   - Output Directory: dist
#   - Development Command: npm run dev

# Set environment variables
vercel env add VITE_SUPABASE_URL production
# Paste: https://cbnrmppejmzwzpjuhoyc.supabase.co

vercel env add VITE_SUPABASE_ANON_KEY production
# Paste your anon key

vercel env add VITE_API_URL production
# Paste your backend URL (Railway URL)

# Deploy to production
vercel --prod
```

---

## 🌐 **Step 3: Connect Custom Domain (boardmint.io)**

### **In Vercel Dashboard:**

1. **Go to Project Settings:**
   - Open your project: `boardmint-pcb-analyzer`
   - Click **"Settings"** tab
   - Click **"Domains"** in left sidebar

2. **Add Domain:**
   - Click **"Add Domain"**
   - Enter: `boardmint.io`
   - Click **"Add"**
   - Also add: `www.boardmint.io`

3. **Configure DNS (In Your Domain Registrar):**
   
   Vercel will show you DNS records to add. Go to your domain registrar (GoDaddy, Namecheap, Cloudflare, etc.)
   
   **Add these DNS records:**
   
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
   
   **OR if Vercel gives you different IPs, use those!**

4. **Wait for DNS Propagation:**
   - Usually 5-30 minutes
   - Check status in Vercel dashboard
   - When ready, you'll see ✅ next to your domain

5. **Enable HTTPS:**
   - Vercel automatically provisions SSL certificate
   - Your site will be available at: `https://boardmint.io`

---

## 🖥️ **Step 4: Deploy Backend to Railway (15 minutes)**

### **Why Railway?**
- Easy Python deployment
- Auto HTTPS
- PostgreSQL included
- $5-20/month usage-based

### **Deploy Backend:**

1. **Go to Railway:**
   - Visit: https://railway.app
   - Sign in with GitHub

2. **Create New Project:**
   - Click **"New Project"**
   - Select **"Deploy from GitHub repo"**
   - Choose: `boardmint12-cloud/boardmint-pcb-analyzer`

3. **Configure Service:**
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

4. **Add Environment Variables:**
   
   In Railway dashboard, go to **Variables** tab and add:
   
   ```
   SUPABASE_URL=https://cbnrmppejmzwzpjuhoyc.supabase.co
   SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   SUPABASE_JWT_SECRET=ESTsszMwxIK3OA1cEe0pTcUc4HfTlxFdWxlsC/PLZwNQ...
   DATABASE_URL=postgresql://postgres:1223pranavA@@db.cbnrmppejmzwzpjuhoyc.supabase.co:5432/postgres
   PYTHON_ENV=production
   BACKEND_HOST=0.0.0.0
   BACKEND_PORT=$PORT
   CORS_ORIGINS=https://boardmint.io,https://www.boardmint.io
   FRONTEND_URL=https://boardmint.io
   ```

5. **Generate Domain:**
   - Railway auto-generates a domain: `your-app.up.railway.app`
   - Copy this URL!

6. **Update Frontend Environment:**
   - Go back to Vercel
   - Settings → Environment Variables
   - Update `VITE_API_URL` to your Railway URL: `https://your-app.up.railway.app`
   - Redeploy frontend (Deployments → Redeploy)

---

## 🔐 **Step 5: Security (CRITICAL!)**

### **⚠️ ROTATE SUPABASE KEYS IMMEDIATELY!**

After deployment, you MUST rotate your Supabase keys:

1. **Go to Supabase Dashboard:**
   - https://supabase.com/dashboard
   - Select your project

2. **Rotate Keys:**
   - Settings → API → **Reset anon key** (copy new key)
   - Settings → API → **Reset service_role key** (copy new key)
   - Settings → Database → **Reset database password** (copy new password)

3. **Update Environment Variables:**
   
   **In Vercel:**
   - Settings → Environment Variables
   - Update `VITE_SUPABASE_ANON_KEY` with new key
   - Redeploy
   
   **In Railway:**
   - Variables tab
   - Update all Supabase keys and database URL
   - Will auto-redeploy

4. **Update CORS in Supabase:**
   - Go to Authentication → URL Configuration
   - Add Site URL: `https://boardmint.io`
   - Add Redirect URLs:
     - `https://boardmint.io/**`
     - `https://www.boardmint.io/**`

---

## ✅ **Step 6: Verify Deployment**

### **Test Checklist:**

```bash
# 1. Check frontend is live
curl https://boardmint.io
# Should return HTML

# 2. Check backend is live
curl https://your-app.up.railway.app/
# Should return: {"status":"healthy","service":"PCB Analyzer API"}

# 3. Test quote submission
# Go to: https://boardmint.io/quote
# Fill out form and submit

# 4. Check Supabase
# Go to Table Editor → quotes table
# Your test quote should appear!

# 5. Test authentication
# Go to: https://boardmint.io/login
# Login with: chahalpranav2312@gmail.com / 1223pranav
# Should redirect to: https://boardmint.io/projects
```

---

## 🎯 **Final Configuration**

### **Update backend config.py:**

Before final deployment, update:

```python
# config.py
cors_origins: list = [
    "https://boardmint.io",
    "https://www.boardmint.io",
    # Remove localhost in production:
    # "http://localhost:5173",
]
```

Commit and push:
```bash
git add backend/config.py
git commit -m "chore: update CORS for production"
git push origin main
```

Railway will auto-redeploy!

---

## 📊 **Deployment URLs**

| Service | URL | Status |
|---------|-----|--------|
| **GitHub** | https://github.com/boardmint12-cloud/boardmint-pcb-analyzer | ✅ |
| **Frontend (Vercel)** | https://boardmint.io | ⏳ |
| **Backend (Railway)** | https://your-app.up.railway.app | ⏳ |
| **Database (Supabase)** | https://cbnrmppejmzwzpjuhoyc.supabase.co | ✅ |

---

## 💰 **Expected Costs**

| Service | Plan | Cost |
|---------|------|------|
| Vercel | Pro | $20/month (or Free hobby) |
| Railway | Starter | $5-20/month usage-based |
| Supabase | Free/Pro | Free (or $25/month Pro) |
| **TOTAL** | | **$5-65/month** |

**Start on free tiers, upgrade as needed!**

---

## 🚨 **Important Notes**

1. **⚠️ Rotate Supabase keys IMMEDIATELY after deployment!**
2. Update `VITE_API_URL` in Vercel after Railway deployment
3. Update `CORS_ORIGINS` in Railway to include boardmint.io
4. Add boardmint.io to Supabase Auth URLs
5. Test quote submission end-to-end
6. Monitor logs for first 24 hours

---

## 📞 **Quick Summary**

**Steps:**
1. ✅ Code pushed to GitHub
2. ⏳ Deploy frontend to Vercel
3. ⏳ Connect boardmint.io domain
4. ⏳ Deploy backend to Railway
5. ⏳ Update environment variables
6. ⏳ Rotate Supabase keys
7. ⏳ Test everything

**Time:** ~30-45 minutes total

---

## 🎉 **You're Ready!**

**Next:** Follow Step 2 to deploy to Vercel!

**Questions?** Check Railway and Vercel docs or let me know!
