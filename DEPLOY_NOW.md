# 🚀 **DEPLOY NOW - Quick Start**

## ✅ **Setup Complete!**

Your project is configured for **full-stack Vercel deployment**.

---

## 🎯 **Deploy in 3 Steps (10 minutes)**

### **Step 1: Go to Vercel**
👉 **https://vercel.com/new**

---

### **Step 2: Import Your Repo**
1. Click **"Import Git Repository"**
2. Select: **`boardmint12-cloud/boardmint-pcb-analyzer`**
3. Click **"Import"**

---

### **Step 3: Add Environment Variables**

In the "Configure Project" screen, add these environment variables:

**Copy and paste this into Vercel:**

```bash
SUPABASE_URL=https://cbnrmppejmzwzpjuhoyc.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNibnJtcHBlam16d3pwanVob3ljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ2NjI0MzEsImV4cCI6MjA4MDIzODQzMX0.i1y_eua8LQWXTYPjsfceWV1XkEf2S49c_S-DnuKunhs
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNibnJtcHBlam16d3pwanVob3ljIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NDY2MjQzMSwiZXhwIjoyMDgwMjM4NDMxfQ.z5p-sFT0T9pN93eePkWa8V50pDy8Vwpzj-5rCDcG_9E
SUPABASE_JWT_SECRET=ESTsszMwxIK3OA1cEe0pTcUc4HfTlxFdWxlsC/PLZwNQyqoCd8z08AKVxbBEWo+ZwIrY1TmMSR90wgcP1bKDjg==
DATABASE_URL=postgresql://postgres:1223pranavA@@db.cbnrmppejmzwzpjuhoyc.supabase.co:5432/postgres
PYTHON_ENV=production
VITE_SUPABASE_URL=https://cbnrmppejmzwzpjuhoyc.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNibnJtcHBlam16d3pwanVob3ljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ2NjI0MzEsImV4cCI6MjA4MDIzODQzMX0.i1y_eua8LQWXTYPjsfceWV1XkEf2S49c_S-DnuKunhs
VITE_API_URL=/api
CORS_ORIGINS=https://boardmint.io,https://www.boardmint.io
FRONTEND_URL=https://boardmint.io
```

**Then click "Deploy"** ✅

---

## 🎉 **That's It!**

Vercel will:
- Build your frontend (React)
- Deploy your backend (Python API)
- Give you a live URL in 3-5 minutes

**You'll get:** `https://boardmint-pcb-analyzer.vercel.app`

---

## 🌐 **Connect Domain (After Deployment)**

### **In Vercel Dashboard:**
1. Go to **Settings → Domains**
2. Add: `boardmint.io`
3. Add: `www.boardmint.io`

### **In Your Domain Registrar:**
```
Type: A
Name: @
Value: 76.76.21.21

Type: CNAME
Name: www
Value: cname.vercel-dns.com
```

**Wait 5-30 minutes** → Live at `https://boardmint.io`! 🚀

---

## ✅ **Test Your Deployment**

### **1. Test API:**
```
https://your-app.vercel.app/api/
```
Should return: `{"status":"healthy",...}`

### **2. Test Frontend:**
```
https://your-app.vercel.app/
```
Should show your homepage

### **3. Test Quote Form:**
```
https://your-app.vercel.app/quote
```
Fill and submit - check Supabase for entry!

---

## 🔐 **CRITICAL: After Deployment**

### **⚠️ ROTATE SUPABASE KEYS (5 minutes)**

**Why?** Current keys are in git history - anyone can see them!

**How:**
1. Go to: https://supabase.com/dashboard
2. Settings → API → **Reset anon key**
3. Settings → API → **Reset service_role key**
4. Settings → Database → **Reset password**
5. Update keys in Vercel environment variables
6. Redeploy

**This is MANDATORY for security!** 🔒

---

## 📊 **What You Get**

| Feature | URL |
|---------|-----|
| **Frontend** | `https://boardmint.io/` |
| **Backend API** | `https://boardmint.io/api/` |
| **Quote Form** | `https://boardmint.io/quote` |
| **Login** | `https://boardmint.io/login` |
| **Dashboard** | `https://boardmint.io/projects` |

**Everything on one domain!** No CORS issues! ✅

---

## 💰 **Cost**

**FREE** on Vercel Hobby plan:
- ✅ Unlimited projects
- ✅ 100GB bandwidth
- ✅ Auto HTTPS
- ✅ Global CDN

**Upgrade to Pro ($20/month) if you need:**
- More bandwidth
- Longer serverless timeout (60s vs 10s)
- Team features

---

## 🆘 **Need Help?**

**Full guide:** See `VERCEL_DEPLOYMENT.md`

**Common issues:**
- Build fails? Check build logs in Vercel
- API 404? Verify `vercel.json` and `api/index.py` exist
- CORS errors? Check `CORS_ORIGINS` environment variable

---

## 🎯 **Deployment Checklist**

- [x] Code pushed to GitHub ✅
- [ ] Deploy to Vercel (Step 1-3 above)
- [ ] Test API endpoint
- [ ] Test frontend
- [ ] Test quote submission
- [ ] Connect boardmint.io domain
- [ ] Update DNS records
- [ ] **Rotate Supabase keys** ⚠️
- [ ] Update environment variables
- [ ] Redeploy
- [ ] Test with custom domain

---

## 🚀 **Ready?**

**Click here:** https://vercel.com/new

**Then:** Import `boardmint12-cloud/boardmint-pcb-analyzer`

**See you on the other side!** 🎉

---

**Time estimate: 10 minutes**  
**After: Rotate keys (5 min)**  
**Total: 15 minutes to live deployment!** ⚡
