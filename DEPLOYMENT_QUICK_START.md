# 🚀 **Quick Start: Deploy BoardMint**

## ✅ **What's Done**

- ✅ Code pushed to GitHub
- ✅ Repository: https://github.com/boardmint12-cloud/boardmint-pcb-analyzer
- ✅ `.gitignore` added (secrets protected)
- ✅ Vercel config created

---

## 🎯 **Next Steps (30 minutes)**

### **1. Deploy Frontend to Vercel (10 min)**

**Go to:** https://vercel.com/new

**Steps:**
1. Click **"Import Git Repository"**
2. Select: `boardmint12-cloud/boardmint-pcb-analyzer`
3. Configure:
   - Framework: **Vite**
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `dist`
4. Add Environment Variables:
   ```
   VITE_SUPABASE_URL=https://cbnrmppejmzwzpjuhoyc.supabase.co
   VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNibnJtcHBlam16d3pwanVob3ljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ2NjI0MzEsImV4cCI6MjA4MDIzODQzMX0.i1y_eua8LQWXTYPjsfceWV1XkEf2S49c_S-DnuKunhs
   VITE_API_URL=https://boardmint-backend.up.railway.app
   ```
5. Click **"Deploy"**

**Result:** You'll get a URL like `boardmint-pcb-analyzer.vercel.app`

---

### **2. Connect Domain boardmint.io (5 min)**

**In Vercel:**
1. Go to project **Settings → Domains**
2. Add domain: `boardmint.io`
3. Add domain: `www.boardmint.io`

**In Your Domain Registrar (GoDaddy/Namecheap/etc):**

Add these DNS records:
```
Type: A
Name: @
Value: 76.76.21.21

Type: CNAME
Name: www
Value: cname.vercel-dns.com
```

**Wait:** 5-30 minutes for DNS propagation

**Test:** https://boardmint.io (will be live!)

---

### **3. Deploy Backend to Railway (10 min)**

**Go to:** https://railway.app/new

**Steps:**
1. Sign in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub"**
3. Select: `boardmint12-cloud/boardmint-pcb-analyzer`
4. Settings:
   - Root Directory: `backend`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add Environment Variables:
   ```
   SUPABASE_URL=https://cbnrmppejmzwzpjuhoyc.supabase.co
   SUPABASE_ANON_KEY=your_anon_key
   SUPABASE_SERVICE_KEY=your_service_key
   SUPABASE_JWT_SECRET=your_jwt_secret
   DATABASE_URL=postgresql://postgres:password@db.cbnrmppejmzwzpjuhoyc.supabase.co:5432/postgres
   PYTHON_ENV=production
   CORS_ORIGINS=https://boardmint.io,https://www.boardmint.io
   FRONTEND_URL=https://boardmint.io
   ```
6. Click **"Deploy"**

**Result:** You'll get a URL like `your-app.up.railway.app`

---

### **4. Update Frontend with Backend URL (2 min)**

**In Vercel:**
1. Go to **Settings → Environment Variables**
2. Find `VITE_API_URL`
3. Update to your Railway URL: `https://your-app.up.railway.app`
4. Go to **Deployments** → Click **"Redeploy"**

---

### **5. Test Everything (3 min)**

✅ **Frontend:** https://boardmint.io  
✅ **Quote Form:** https://boardmint.io/quote  
✅ **Login:** https://boardmint.io/login  
✅ **Backend API:** https://your-app.up.railway.app/

**Test Flow:**
1. Go to https://boardmint.io/quote
2. Fill out quote form
3. Submit
4. Check Supabase → Table Editor → quotes
5. See your quote!

---

## 🔐 **CRITICAL: Rotate Keys After Deployment**

⚠️ **DO THIS IMMEDIATELY:**

1. Go to Supabase Dashboard
2. Settings → API → **Reset anon key**
3. Settings → API → **Reset service_role key**
4. Settings → Database → **Reset password**
5. Update keys in both Vercel and Railway
6. Redeploy both

**Why?** Your current keys are in git history. Anyone with access can use them!

---

## 📊 **Deployment Checklist**

- [ ] Deploy frontend to Vercel
- [ ] Add boardmint.io domain to Vercel
- [ ] Update DNS records at domain registrar
- [ ] Deploy backend to Railway
- [ ] Add all environment variables to Railway
- [ ] Update VITE_API_URL in Vercel
- [ ] Redeploy frontend
- [ ] Test quote submission
- [ ] Test login
- [ ] **Rotate all Supabase keys**
- [ ] Update environment variables with new keys
- [ ] Monitor logs for 24 hours

---

## 🎯 **Quick Links**

| Service | URL |
|---------|-----|
| **GitHub Repo** | https://github.com/boardmint12-cloud/boardmint-pcb-analyzer |
| **Deploy Frontend** | https://vercel.com/new |
| **Deploy Backend** | https://railway.app/new |
| **Supabase Dashboard** | https://supabase.com/dashboard |
| **Your Domain** | https://boardmint.io |

---

## 💡 **Tips**

- **Vercel deployment:** Usually takes 2-3 minutes
- **Railway deployment:** Usually takes 3-5 minutes
- **DNS propagation:** Can take up to 30 minutes
- **Free tiers available:** Start with Vercel Hobby + Railway Free

---

## 🆘 **Troubleshooting**

**Frontend won't build?**
- Check build logs in Vercel
- Make sure `frontend/package.json` has `"build": "vite build"`

**Backend won't start?**
- Check logs in Railway
- Verify all environment variables are set
- Check `CORS_ORIGINS` includes your domain

**Domain not working?**
- DNS can take up to 48 hours (usually 30 min)
- Check DNS with: `dig boardmint.io`
- Verify records in registrar

**Quote form not working?**
- Check browser console for errors
- Verify `VITE_API_URL` is correct
- Test backend directly: `curl https://your-railway-url.up.railway.app/`

---

## 🎉 **You're Ready!**

**Start here:** Step 1 - Deploy to Vercel

**Full guide:** See `DEPLOY_TO_VERCEL.md`

**Questions?** The deployment is straightforward - just follow the steps!

---

**Estimated time: 30 minutes** ⏱️

**After deployment: ROTATE KEYS!** 🔐
