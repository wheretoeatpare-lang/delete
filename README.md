# 🦴 SEO Monitor — GitHub Actions + Groq

Daily SEO checker that runs automatically via GitHub Actions and emails you a report!

---

## 📁 Files to Upload to GitHub

```
your-repo/
├── .github/
│   └── workflows/
│       └── seo-monitor.yml   ← GitHub Actions schedule
├── seo-monitor/
│   ├── run.js                ← Main script
│   └── sites.js              ← YOUR SITES GO HERE
└── package.json
```

---

## 🚀 Setup Steps

### 1. Add your sites
Edit `seo-monitor/sites.js`:
```js
module.exports = [
  "https://yoursite.com",
  "https://anothersite.com",
];
```

### 2. Get a Groq API key
- Go to https://console.groq.com
- Create a free account → API Keys → Create key
- Copy the key

### 3. Set up Gmail App Password
- Go to your Google Account → Security → 2-Step Verification → App passwords
- Create one for "Mail" → copy the 16-char password

### 4. Add GitHub Secrets
Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 4 secrets:

| Secret Name   | Value                          |
|---------------|-------------------------------|
| `GROQ_API_KEY`| Your Groq API key             |
| `EMAIL_USER`  | your.gmail@gmail.com          |
| `EMAIL_PASS`  | Your Gmail App Password       |
| `EMAIL_TO`    | Where to send the report      |

### 5. Push to GitHub
```bash
git init
git add .
git commit -m "Add SEO monitor"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 6. Change the schedule (optional)
In `.github/workflows/seo-monitor.yml`, edit the cron line:
```yaml
- cron: "0 8 * * *"   # 8:00 AM UTC every day
```
Use https://crontab.guru to customize the time.

### 7. Test it manually
Go to your repo → **Actions** tab → **Daily SEO Monitor** → **Run workflow**

---

## 🆓 Free Tier Limits

- **Groq**: Very generous free tier, fast inference
- **GitHub Actions**: 2,000 free minutes/month (this uses ~1–2 min/day)
- **Gmail SMTP**: Free with App Password

---

Powered by Groq AI (llama-3.3-70b) 🦴
