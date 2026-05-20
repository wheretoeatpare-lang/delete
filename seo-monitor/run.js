const Groq = require("groq-sdk");
const nodemailer = require("nodemailer");
const sites = require("./sites");

// ── Groq client ──────────────────────────────────────────────────────────────
const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const SEO_CHECKS = [
  { id: "schema",     label: "Schema Markup"      },
  { id: "faq_schema", label: "FAQ Schema"          },
  { id: "h1",         label: "H1 Tag"              },
  { id: "h2",         label: "H2 Tags"             },
  { id: "h3",         label: "H3 Tags"             },
  { id: "meta_title", label: "Meta Title"          },
  { id: "meta_desc",  label: "Meta Description"    },
  { id: "alt_text",   label: "Image Alt Text"      },
  { id: "canonical",  label: "Canonical Tag"       },
  { id: "og_tags",    label: "OG / Social Tags"    },
  { id: "robots",     label: "Robots Meta"         },
  { id: "sitemap",    label: "Sitemap"             },
];

// ── SEO check via Groq ───────────────────────────────────────────────────────
async function runSEOCheck(url) {
  const completion = await groq.chat.completions.create({
    model: "llama-3.3-70b-versatile", // fast + smart model on Groq
    max_tokens: 1000,
    response_format: { type: "json_object" }, // Groq supports JSON mode!
    messages: [
      {
        role: "system",
        content: `You are an SEO auditor. The user gives you a URL. Analyze its SEO and return ONLY a valid JSON object.

Return exactly this shape:
{
  "schema": true/false,
  "faq_schema": true/false,
  "h1": true/false,
  "h2": true/false,
  "h3": true/false,
  "meta_title": true/false,
  "meta_desc": true/false,
  "alt_text": true/false,
  "canonical": true/false,
  "og_tags": true/false,
  "robots": true/false,
  "sitemap": true/false,
  "issues": ["list", "of", "specific", "problems"],
  "score": 0-100,
  "summary": "One sentence overall summary"
}

true = check passes, false = check fails/missing. Base your analysis on common SEO practices for the given URL domain/type.`,
      },
      {
        role: "user",
        content: `Audit the SEO of this website: ${url}`,
      },
    ],
  });

  const text = completion.choices[0]?.message?.content || "{}";
  return JSON.parse(text);
}

// ── Score badge for email ────────────────────────────────────────────────────
function scoreBadge(score) {
  if (score >= 80) return { color: "#16a34a", bg: "#dcfce7", label: "Good" };
  if (score >= 50) return { color: "#d97706", bg: "#fef3c7", label: "Fair" };
  return { color: "#dc2626", bg: "#fee2e2", label: "Poor" };
}

// ── Build HTML email ─────────────────────────────────────────────────────────
function buildEmailHTML(results) {
  const date = new Date().toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });

  const siteCards = results.map(({ url, result, error }) => {
    if (error) {
      return `
        <div style="margin-bottom:20px;padding:16px;border:1px solid #fca5a5;border-radius:8px;background:#fff1f2;">
          <strong style="color:#dc2626;">❌ ${url}</strong>
          <p style="margin:8px 0 0;color:#7f1d1d;font-size:13px;">Check failed: ${error}</p>
        </div>`;
    }

    const badge = scoreBadge(result.score || 0);
    const checksHTML = SEO_CHECKS.map(c => {
      const pass = result[c.id];
      return `<span style="display:inline-block;margin:3px;padding:3px 8px;border-radius:4px;font-size:11px;
        background:${pass ? "#dcfce7" : "#fee2e2"};color:${pass ? "#15803d" : "#b91c1c"};">
        ${pass ? "✓" : "✗"} ${c.label}
      </span>`;
    }).join("");

    const issuesHTML = result.issues?.length
      ? `<div style="margin-top:10px;">
          <strong style="font-size:12px;color:#6b7280;">Issues found:</strong>
          <ul style="margin:6px 0 0;padding-left:18px;">
            ${result.issues.map(i => `<li style="font-size:12px;color:#b45309;margin-bottom:4px;">${i}</li>`).join("")}
          </ul>
        </div>`
      : "";

    return `
      <div style="margin-bottom:20px;padding:16px;border:1px solid #e5e7eb;border-radius:8px;background:#fff;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
          <strong style="font-size:14px;color:#111827;">${url}</strong>
          <span style="padding:4px 10px;border-radius:20px;font-size:12px;font-weight:600;
            background:${badge.bg};color:${badge.color};">
            ${result.score}/100 — ${badge.label}
          </span>
        </div>
        ${result.summary ? `<p style="margin:0 0 10px;font-size:13px;color:#6b7280;font-style:italic;">${result.summary}</p>` : ""}
        <div>${checksHTML}</div>
        ${issuesHTML}
      </div>`;
  }).join("");

  const avgScore = results
    .filter(r => r.result)
    .reduce((a, r) => a + (r.result.score || 0), 0) / (results.filter(r => r.result).length || 1);

  return `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;margin:0;padding:0;">
  <div style="max-width:600px;margin:0 auto;padding:24px;">
    <div style="background:#111827;border-radius:12px;padding:24px;margin-bottom:20px;text-align:center;">
      <h1 style="color:#fff;margin:0;font-size:22px;">🔍 Daily SEO Report</h1>
      <p style="color:#9ca3af;margin:8px 0 0;font-size:13px;">${date}</p>
    </div>

    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px;">
      <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#111827;">${results.length}</div>
        <div style="font-size:12px;color:#6b7280;">Sites Checked</div>
      </div>
      <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:${scoreBadge(avgScore).color};">${Math.round(avgScore)}</div>
        <div style="font-size:12px;color:#6b7280;">Avg Score</div>
      </div>
      <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#dc2626;">${results.reduce((a, r) => a + (r.result?.issues?.length || 0), 0)}</div>
        <div style="font-size:12px;color:#6b7280;">Total Issues</div>
      </div>
    </div>

    ${siteCards}

    <p style="font-size:11px;color:#9ca3af;text-align:center;margin-top:20px;">
      Powered by Groq AI + GitHub Actions 🦴
    </p>
  </div>
</body>
</html>`;
}

// ── Send email via Gmail ─────────────────────────────────────────────────────
async function sendEmail(html, siteCount) {
  const transporter = nodemailer.createTransport({
    service: "gmail",
    auth: {
      user: process.env.EMAIL_USER,
      pass: process.env.EMAIL_PASS, // Use Gmail App Password!
    },
  });

  await transporter.sendMail({
    from: `"SEO Monitor 🔍" <${process.env.EMAIL_USER}>`,
    to: process.env.EMAIL_TO,
    subject: `📊 Daily SEO Report — ${siteCount} site${siteCount !== 1 ? "s" : ""} checked`,
    html,
  });
}

// ── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  console.log(`🦴 Caveman start SEO check! Checking ${sites.length} site(s)...`);

  if (!sites.length) {
    console.error("❌ No sites in seo-monitor/sites.js! Add some URLs.");
    process.exit(1);
  }

  const results = [];

  for (const url of sites) {
    console.log(`  → Checking: ${url}`);
    try {
      const result = await runSEOCheck(url);
      console.log(`     Score: ${result.score}/100`);
      results.push({ url, result });
    } catch (err) {
      console.error(`     Failed: ${err.message}`);
      results.push({ url, error: err.message });
    }
  }

  console.log("🦴 Caveman build email report...");
  const html = buildEmailHTML(results);

  console.log("🦴 Caveman send email!");
  try {
    await sendEmail(html, sites.length);
    console.log(`✅ Email sent to ${process.env.EMAIL_TO}`);
  } catch (err) {
    console.error("❌ Email failed:", err.message);
    process.exit(1);
  }
}

main();
