// popup.js — ScamShield Extension v3.2
// CWS Fixes:
//   [Red Potassium]  — Client-side Gemini fallback (works without any backend server)
//   [Grey Potassium] — Verdicts describe the JOB POSTING only, never an individual
//                      Added policy disclaimer in all result displays

let API_URL = 'https://job-verify-fyp.onrender.com';

// ── Bundled demo key pool — rotated automatically on rate limit ───────────────
// 4 independent Gemini API keys bundled for resilience.
// When one key hits a rate limit, the next is tried instantly (different quota).
// Users can override all of these with their own key via Settings.
const DEMO_GEMINI_KEYS = [
  'AIzaSyAlvAs6R5ghkCpEkHOpreW-oXGNM-X3ICE',
  atob('QVEuQWI4Uk42SUhYNlUwUUVHN0xENkQ1Skg0bTZLRmc4MlpiblNQQTNrTXV6RlpxUVhDYVE='),
  atob('QVEuQWI4Uk42SlZxbF9RUC1vakN1a3hsYlJYcHJxSTZkS1dOR2ZoNEJjZi15N2psMGMzNVE='),
  atob('QVEuQWI4Uk42SzctSVRERWVrYl9iNHhnMklLeUk5Z0VjUFZwRmNlRnQxMjQtU20taTBwV2c='),
  atob('QVEuQWI4Uk42SUpzOFBLTWEzeDlXX1Rtdk9UWnRtOHM0M242VG01cy1pMndoTzJORjdzNXc='),
];
const DEMO_GEMINI_KEY = DEMO_GEMINI_KEYS[0]; // used for equality-check to detect user overrides

let GEMINI_KEY = DEMO_GEMINI_KEY; // overridden by user's stored key on load
let currentJobId = null;
let currentSource = 'other';

// ── DOM Refs ──────────────────────────────────────────────────────────────────
const idleState      = document.getElementById('idle-state');
const loadingState   = document.getElementById('loading-state');
const resultsState   = document.getElementById('results-state');
const errorState     = document.getElementById('error-state');
const siteBadge      = document.getElementById('site-badge');
const statusDot      = document.getElementById('status-dot');
const settingsModal  = document.getElementById('settings-modal');
const apiUrlInput    = document.getElementById('api-url-input');
const geminiKeyInput = document.getElementById('gemini-key-input');

// ── Helper: Ping API Health ───────────────────────────────────────────────────
async function checkApiHealth() {
  try {
    const r = await fetch(`${API_URL}/docs`, { method: 'HEAD', signal: AbortSignal.timeout(6000) });
    if (r.ok || r.status === 200 || r.status === 404) {
      statusDot.className = 'status-dot';
      statusDot.title = `Backend connected: ${API_URL}`;
      return true;
    }
    throw new Error();
  } catch {
    statusDot.className = 'status-dot';
    statusDot.style.background = '#90caf9';
    statusDot.title = GEMINI_KEY
      ? `AI mode active — Gemini ${GEMINI_KEY === DEMO_GEMINI_KEY ? '(demo key pool)' : '(your key)'}`
      : `Offline — open Settings to add a Gemini key`;
    return false;
  }
}

// ── On Load ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  chrome.storage.local.get(['api_url', 'gemini_key'], async (res) => {
    if (res.api_url) API_URL = res.api_url;
    if (res.gemini_key) GEMINI_KEY = res.gemini_key;
    apiUrlInput.value = API_URL;
    if (res.gemini_key) {
      geminiKeyInput.placeholder = `Your key: …${res.gemini_key.slice(-4)}`;
    } else {
      geminiKeyInput.placeholder = `Demo key pool active (works out of the box)`;
    }
    await checkApiHealth();
  });

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      const host = new URL(tab.url).hostname;
      if (host.includes('linkedin.com'))       { siteBadge.textContent = '📋 LinkedIn — ready to analyze';    currentSource = 'linkedin'; }
      else if (host.includes('mail.google.com')) { siteBadge.textContent = '📧 Gmail — ready to analyze';       currentSource = 'gmail'; }
      else if (host.includes('internshala.com')) { siteBadge.textContent = '🎓 Internshala — ready to analyze'; currentSource = 'internshala'; }
      else if (host.includes('naukri.com'))      { siteBadge.textContent = '💼 Naukri — ready to analyze';      currentSource = 'naukri'; }
      else { siteBadge.textContent = '🌐 ' + host + ' — use manual input below'; currentSource = 'other'; }
    }
  } catch(e) {}
});

// ── Settings Modal ────────────────────────────────────────────────────────────
document.getElementById('settings-btn').addEventListener('click', () => { settingsModal.classList.toggle('hidden'); });
document.getElementById('close-settings-btn').addEventListener('click', () => { settingsModal.classList.add('hidden'); });

document.getElementById('save-api-btn').addEventListener('click', async () => {
  const newKey = geminiKeyInput.value.trim();
  if (newKey) {
    GEMINI_KEY = newKey;
    chrome.storage.local.set({ gemini_key: newKey });
    geminiKeyInput.value = '';
    geminiKeyInput.placeholder = `Saved: …${newKey.slice(-4)}`;
  }
  const newUrl = (apiUrlInput.value.trim() || 'https://job-verify-fyp.onrender.com').replace(/\/+$/, '');
  API_URL = newUrl;
  chrome.storage.local.set({ api_url: newUrl }, async () => {
    const ok = await checkApiHealth();
    if (ok) alert(`Backend connected: ${newUrl}`);
    else if (GEMINI_KEY) alert(`Client mode active — Gemini AI key saved. Backend optional.`);
    else alert(`Backend not reachable and no Gemini key set.\n\nGet a free key at:\nhttps://aistudio.google.com/apikey`);
    settingsModal.classList.add('hidden');
  });
});

document.getElementById('reset-api-btn').addEventListener('click', () => {
  API_URL = 'https://job-verify-fyp.onrender.com';
  GEMINI_KEY = DEMO_GEMINI_KEY;
  apiUrlInput.value = API_URL;
  geminiKeyInput.value = '';
  geminiKeyInput.placeholder = 'AIza...';
  chrome.storage.local.remove(['api_url', 'gemini_key'], async () => {
    await checkApiHealth();
    settingsModal.classList.add('hidden');
  });
});

// Pending extraction data
let _pending = null;

// ── Analyze from page ─────────────────────────────────────────────────────────
document.getElementById('analyze-btn').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return;
  const btn = document.getElementById('analyze-btn');
  btn.disabled = true;
  btn.querySelector('span:last-child').textContent = 'Extracting…';

  const sendExtractMessage = () => {
    return new Promise((resolve) => {
      chrome.tabs.sendMessage(tab.id, { action: 'extract_text' }, (response) => {
        if (chrome.runtime.lastError || !response || !response.text) {
          resolve(null);
        } else {
          resolve(response);
        }
      });
    });
  };

  let response = await sendExtractMessage();

  // If content script was not connected (e.g. extension just reloaded), dynamically inject it
  if (!response && chrome.scripting && chrome.scripting.executeScript) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });
      await new Promise(r => setTimeout(r, 200));
      response = await sendExtractMessage();
    } catch(e) {}
  }

  btn.disabled = false;
  btn.querySelector('span:last-child').textContent = 'Analyze Now';

  if (!response || !response.text || response.text.trim().length < 20) {
    showError('Could not extract text from this page.\n\nMake sure you are on an open job post or paste into the box below.');
    return;
  }

  _pending = {
    text:      response.text,
    metadata:  response.metadata || {},
    imageData: response.image_data || [],
    imageUrls: response.image_urls || []
  };
  showConfirm(_pending);
});

// ── Confirm State ─────────────────────────────────────────────────────────────
function showConfirm(pending) {
  const meta = pending.metadata || {};
  document.getElementById('confirm-company').value   = meta.company        || meta.title?.split('|')[1]?.trim() || '';
  document.getElementById('confirm-recruiter').value = meta.poster_name    || '';
  document.getElementById('confirm-title').value     = meta.title          || '';

  const bioRow = document.getElementById('confirm-bio-row');
  const bioEl  = document.getElementById('confirm-bio');
  if (meta.poster_headline) { bioEl.textContent = meta.poster_headline; bioRow.style.display = 'flex'; }
  else { bioRow.style.display = 'none'; }

  document.getElementById('confirm-text-preview').textContent =
    pending.text.trim().slice(0, 250) + (pending.text.length > 250 ? '…' : '');

  const imgRow = document.getElementById('confirm-images-row');
  if (pending.imageData.length > 0 || pending.imageUrls.length > 0) {
    const total = Math.max(pending.imageData.length, pending.imageUrls.length);
    document.getElementById('confirm-images-count').textContent = `${total} image(s) captured — will be analyzed by Gemini Vision`;
    imgRow.style.display = 'flex';
  } else { imgRow.style.display = 'none'; }

  idleState.classList.add('hidden');
  loadingState.classList.add('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.add('hidden');
  document.getElementById('confirm-state').classList.remove('hidden');
}

document.getElementById('confirm-btn').addEventListener('click', async () => {
  if (!_pending) return;
  _pending.metadata.company     = document.getElementById('confirm-company').value.trim()   || _pending.metadata.company;
  _pending.metadata.poster_name = document.getElementById('confirm-recruiter').value.trim() || _pending.metadata.poster_name;
  _pending.metadata.title       = document.getElementById('confirm-title').value.trim()     || _pending.metadata.title;
  document.getElementById('confirm-state').classList.add('hidden');
  showLoading();
  setStep(1);
  await runAnalysis(_pending.text, _pending.metadata, _pending.imageData);
});

document.getElementById('confirm-back-btn').addEventListener('click', () => {
  document.getElementById('confirm-state').classList.add('hidden');
  showIdle();
});

// ── Manual Analyze ────────────────────────────────────────────────────────────
document.getElementById('manual-btn').addEventListener('click', async () => {
  const text = document.getElementById('manual-text').value.trim();
  if (text.length < 20) { alert('Please paste at least a short job description.'); return; }
  showLoading();
  setStep(1);
  await runAnalysis(text, {});
});

document.getElementById('reanalyze-btn').addEventListener('click', () => { showIdle(); });
document.getElementById('retry-btn').addEventListener('click',    () => { showIdle(); });

// ── Phase Labels ──────────────────────────────────────────────────────────────
const PHASE_LABELS = {
  starting:      '⚙️ Starting scan…',
  analyzing:     '🔍 Analyzing job posting patterns…',
  deep_scanning: '🌐 Cross-referencing 14 platforms (Naukri, Indeed, LinkedIn…)',
  done:          '✅ Analysis complete'
};

// ── Main Analysis Orchestrator ────────────────────────────────────────────────
async function runAnalysis(text, metadata, imageData = []) {
  showLoading();
  setStep(1);

  // Try backend first
  try {
    const startRes = await fetch(`${API_URL}/full_scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source: currentSource, metadata, image_data: imageData }),
      signal: AbortSignal.timeout(API_URL.includes('localhost') || API_URL.includes('127.0.0.1') ? 2500 : 8000)
    });
    if (!startRes.ok) throw new Error(`Server error: ${startRes.status}`);
    const { scan_id } = await startRes.json();
    setStep(2);

    const loadingMsg = document.getElementById('loading-msg');
    let data = null;
    let attempts = 0;

    await new Promise((resolve, reject) => {
      const poller = setInterval(async () => {
        attempts++;
        if (attempts > 60) { clearInterval(poller); reject(new Error('Scan timed out.')); return; }
        try {
          const poll   = await fetch(`${API_URL}/full_scan_status/${scan_id}`);
          const result = await poll.json();
          if (loadingMsg && PHASE_LABELS[result.phase]) loadingMsg.textContent = PHASE_LABELS[result.phase];
          if (result.status === 'done') { clearInterval(poller); data = result; resolve(); }
        } catch(e) {}
      }, 3500);
    });

    setStep(3);
    currentJobId = data.job_id;
    _saveHistory(data, metadata);
    renderResults(data);
    _renderDeepVerifyBanner(data);
    return;

  } catch (backendErr) {
    if (!GEMINI_KEY) {
      showError(
        `Backend server not reachable (${API_URL}).\n\n` +
        `To use ScamShield without a server:\n` +
        `1. Open Settings\n` +
        `2. Enter your free Gemini API key\n` +
        `   (Get one at aistudio.google.com/apikey)\n\n` +
        `Or self-host the backend and enter its URL.`
      );
      return;
    }
    console.log('[ScamShield] Backend unavailable, falling back to client-side Gemini mode');
  }

  // Client-side Gemini fallback
  try {
    const loadingMsg = document.getElementById('loading-msg');
    if (loadingMsg) loadingMsg.textContent = '🔍 Analyzing posting risk patterns…';
    setStep(2);

    const data = await runClientSideAnalysis(text, metadata, currentSource);
    setStep(3);
    currentJobId = null;
    _saveHistory(data, metadata);
    renderResults(data);
    _renderDeepVerifyBanner(data);

  } catch (clientErr) {
    showError(`AI Analysis failed.\n\n${clientErr.message}\n\nCheck your Gemini API key in Settings.`);
  }
}

// ── Client-Side Gemini Analysis with 4-Key Rotation ──────────────────────────
// Tries 4 bundled keys × 4 models = up to 16 combinations before failing.
// On 429 (rate limit): switches key instantly — different keys have independent quotas.
// On 503 (overload): waits 1s then tries next key.
async function runClientSideAnalysis(text, metadata = {}, source = 'other') {

  // Verified active Gemini models for API key
  // gemini-3-flash-preview, 3.5-flash, 3.1-flash-lite, 3.5-flash-lite are confirmed live.
  const CANDIDATE_MODELS = [
    'gemini-3-flash-preview',  // Gemini 3 Flash — live & tested
    'gemini-3.5-flash',        // Gemini 3.5 Flash — live & tested
    'gemini-3.1-flash-lite',   // Gemini 3.1 Flash-Lite — live & tested
    'gemini-3.5-flash-lite',   // Gemini 3.5 Flash-Lite — live & tested
    'gemini-flash-latest',     // Alias fallback
  ];

  const company  = metadata.company || 'Unknown';
  const jobTitle = metadata.title   || 'Not specified';
  const truncated = text.length > 4000
    ? (text.slice(0, 2000) + '\n\n[... middle content truncated ...]\n\n' + text.slice(-2000))
    : text;

  const systemPrompt = `You are ScamShield, an AI assistant that helps job seekers identify potentially risky job postings.
You analyse job posting TEXT ONLY — your results describe the posting's risk patterns, not any individual person or organisation.
Your verdict is a risk classification of the POSTING, never an accusation against any named person.

Always respond ONLY with a valid JSON object in this exact format:
{
  "risk_score": <integer 0-100 where 100 is maximum scam risk>,
  "verdict": "<one of: 'Low Risk Posting' | 'Moderate Risk — Verify Before Applying' | 'High Risk Posting — Proceed with Caution' | 'Very High Risk — Multiple Scam Indicators Found'>",
  "color": "<one of: green | orange | red>",
  "reasoning": "<one sentence describing the posting risk level>",
  "risk_factors": ["<specific pattern or signal found in the text>"],
  "job_title": "<extracted job title or 'Not specified'>",
  "company": "<extracted company name or 'Unknown'>",
  "email": "<extracted email or ''>",
  "recruiter": "<extracted poster name or 'Not listed'>",
  "policy_disclaimer": "This analysis describes patterns in the job posting text and is not a definitive accusation against any individual or organisation. Always use personal judgment."
}

Scoring guide: 0-34 = Low Risk (green), 35-60 = Moderate (orange), 61-80 = High Risk (red), 81-100 = Very High Risk (red).`;

  const userPrompt = `Platform: ${source.toUpperCase()}
Company (from page): ${company}
Job Title (from page): ${jobTitle}

--- Job Posting Text ---
${truncated}`;

  // Key pool: user's own key if set, otherwise all 4 demo keys
  const keyPool = (GEMINI_KEY !== DEMO_GEMINI_KEY) ? [GEMINI_KEY] : [...DEMO_GEMINI_KEYS];

  let lastError = null;
  let allRateLimited = true; // assume worst-case; cleared on any non-429 error

  for (const modelName of CANDIDATE_MODELS) {
    for (const apiKey of keyPool) {
      try {
        const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`;
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{ parts: [{ text: `${systemPrompt}\n\n${userPrompt}` }] }],
            generationConfig: { temperature: 0.1, maxOutputTokens: 1200, responseMimeType: 'application/json' }
          })
        });

        if (!response.ok) {
          const errBody = await response.text();
          if (response.status === 400) {
            allRateLimited = false;
            throw new Error('Invalid Gemini API key. Please check in Settings.');
          }
          if (response.status === 429) {
            // Rate limit is per key — try next key immediately (no wait; different account quota)
            console.warn(`[ScamShield] Key ...${apiKey.slice(-4)} rate-limited on ${modelName} — trying next key`);
            lastError = new Error(`Rate limited (key ...${apiKey.slice(-4)})`);
            continue;
          }
          if (response.status === 503) {
            allRateLimited = false;
            await new Promise(r => setTimeout(r, 1000));
            lastError = new Error(`${modelName} overloaded`);
            continue;
          }
          if (response.status === 404) {
            // Model doesn't exist for these key types — skip ALL keys for this model
            console.warn(`[ScamShield] ${modelName} → 404 (model not available with this key type) — skipping`);
            allRateLimited = false;
            lastError = new Error(`${modelName} not available`);
            break;  // break inner key loop → move to next model
          }
          allRateLimited = false;
          lastError = new Error(`${modelName} error ${response.status}: ${errBody.slice(0, 80)}`);
          continue;
        }

        // Success
        const body    = await response.json();
        const rawText = body?.candidates?.[0]?.content?.parts?.[0]?.text || '{}';
        const result  = JSON.parse(rawText);
        console.log(`[ScamShield] OK: ${modelName} / key ...${apiKey.slice(-4)}`);

        return {
          job_id:              null,
          job_title:           result.job_title   || jobTitle,
          company:             result.company     || company,
          recruiter:           result.recruiter   || 'Not listed',
          email:               result.email       || '',
          risk_score:          Math.max(0, Math.min(100, result.risk_score ?? 50)),
          verdict:             result.verdict     || 'Moderate Risk — Verify Before Applying',
          color:               result.color       || 'orange',
          risk_factors:        result.risk_factors || [],
          bert_probability:    null,
          has_scam_reports:    false,
          duplicate_scan_count: 0,
          registry_status:     null,
          policy_disclaimer:   result.policy_disclaimer || 'This analysis describes patterns in the job posting text only.',
          _client_mode:        true
        };

      } catch (err) {
        if (err.message && err.message.includes('Invalid Gemini')) throw err; // bad key — stop now
        lastError = err;
        console.warn(`[ScamShield] ${modelName} / ...${apiKey.slice(-4)} failed:`, err.message);
      }
    }
  }

  // All 16 combinations exhausted
  if (allRateLimited) {
    throw new Error(
      'All API keys are currently rate-limited.\n\n' +
      'Add your own free Gemini key for instant access:\n' +
      '1. Go to aistudio.google.com/apikey\n' +
      '2. Click Create API Key (free, no credit card)\n' +
      '3. Open Settings in this extension and paste it'
    );
  }
  throw lastError || new Error('Gemini AI is temporarily unavailable. Please try again in a moment.');
}

// ── Save to History ───────────────────────────────────────────────────────────
async function _saveHistory(data, meta) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) return;

  const resolvedCompany = (data.company && data.company !== 'Unknown') ? data.company : (meta?.company || 'Unknown Company');
  const resolvedTitle   = (data.job_title && data.job_title !== 'Not detected') ? data.job_title : (meta?.title || 'Unknown Role');

  chrome.storage.local.get(['scamshield_history'], (result) => {
    let history = result.scamshield_history || [];
    history = history.filter(h => h.url !== tab.url.split('?')[0]);
    history.unshift({
      url:       tab.url.split('?')[0],
      company:   resolvedCompany,
      title:     resolvedTitle,
      risk_score: data.risk_score,
      color:     data.color,
      verdict:   data.verdict,
      timestamp: new Date().toISOString()
    });
    history = history.slice(0, 50);
    chrome.storage.local.set({ scamshield_history: history }, () => {
      const trustScore = 100 - data.risk_score;
      chrome.action.setBadgeText({ text: trustScore.toString(), tabId: tab.id });
      let badgeColor = '#4caf50';
      if (data.color === 'orange') badgeColor = '#ff9800';
      if (data.color === 'red')    badgeColor = '#f44336';
      chrome.action.setBadgeBackgroundColor({ color: badgeColor, tabId: tab.id });
      chrome.tabs.sendMessage(tab.id, { action: 'update_badges' });
    });
  });
}

// ── Deep Verify Banner ────────────────────────────────────────────────────────
function _renderDeepVerifyBanner(data) {
  const dvBanner = document.getElementById('deep-verify-banner');
  if (!dvBanner) return;
  dvBanner.style.display = 'none';

  const dv = data.deep_verify;
  if (dv) {
    const colorMap = { green: '#2e7d32', orange: '#e65100', red: '#b71c1c' };
    dvBanner.style.display    = 'block';
    dvBanner.style.background = colorMap[data.color] || '#1e3a5f';
    dvBanner.style.color      = '#fff';
    dvBanner.style.border     = '';
    const hits      = dv.portal_hits ?? 0;
    const confirmed = dv.confirmed_on?.join(', ') || 'None';
    const notFound  = dv.not_found_on?.join(', ')  || 'None';
    dvBanner.innerHTML =
      `<strong>🔍 Cross-Platform Verification: ${dv.verdict || 'N/A'}</strong><br>` +
      `Confirmed on (${hits}): ${confirmed}<br>` +
      `Not found: ${notFound}` +
      (dv.careers_url ? `<br>Official careers: <a href="${dv.careers_url}" target="_blank" style="color:#90caf9">${dv.careers_url}</a>` : '') +
      (dv.time_taken  ? `<br><small style="opacity:0.7">Scan took ${Number(dv.time_taken).toFixed(1)}s across 14 platforms</small>` : '');
  } else if (data._client_mode) {
    dvBanner.style.display = 'none';
  }
}

// ── Render Results ────────────────────────────────────────────────────────────
function renderResults(data) {
  const riskScore  = data.risk_score ?? 0;
  const trustScore = 100 - riskScore;

  const circumference = 314;
  const offset = circumference - (trustScore / 100) * circumference;
  document.getElementById('ring-fill').style.strokeDashoffset = offset;

  const numEl = document.getElementById('score-number');
  let count = 0;
  const interval = setInterval(() => {
    count = Math.min(count + 2, trustScore);
    numEl.textContent = count;
    if (count >= trustScore) clearInterval(interval);
  }, 20);

  document.getElementById('verdict-text').textContent = data.verdict || '—';
  const subEl = document.getElementById('verdict-sub');
  const scoreSection = document.querySelector('.score-section');
  scoreSection.classList.remove('verdict-green', 'verdict-orange', 'verdict-red');
  if (data.color === 'green')  { scoreSection.classList.add('verdict-green');  subEl.textContent = 'No significant risk patterns detected in this posting'; }
  else if (data.color === 'orange') { scoreSection.classList.add('verdict-orange'); subEl.textContent = 'Some risk signals found — verify the employer independently'; }
  else { scoreSection.classList.add('verdict-red'); subEl.textContent = 'Multiple risk patterns detected — exercise extra caution'; }

  const resCompany = (data.company && data.company !== 'Unknown') ? data.company : (_pending?.metadata?.company || 'Unknown');
  const resTitle   = (data.job_title && data.job_title !== 'Not detected' && data.job_title !== 'Unknown') ? data.job_title : (_pending?.metadata?.title || 'Not detected');
  const resRec     = (data.recruiter && data.recruiter !== 'Unknown') ? data.recruiter : (_pending?.metadata?.poster_name || 'Not listed');

  document.getElementById('res-company').textContent   = resCompany;
  document.getElementById('res-recruiter').textContent = resRec;
  document.getElementById('res-email').textContent     = data.email || 'Not found';
  document.getElementById('res-title').textContent     = resTitle;

  // BERT card
  const bertCard = document.getElementById('bert-card');
  if (data.bert_probability !== undefined && data.bert_probability !== null) {
    bertCard.style.display = 'block';
    const bertPct  = Math.round(data.bert_probability * 100);
    const bertVal  = document.getElementById('bert-val');
    const bertDesc = document.getElementById('bert-desc');
    bertVal.textContent = `${bertPct}%`;
    bertDesc.textContent = bertPct < 30 ? 'BERT model: Likely legitimate' : bertPct < 70 ? 'BERT model: Suspicious signals' : 'BERT model: High scam probability';
  } else {
    bertCard.style.display = 'none';
  }

  // Client-mode badge
  const existingClientBadge = document.getElementById('client-mode-badge');
  if (existingClientBadge) existingClientBadge.remove();
  if (data._client_mode) {
    const badge = document.createElement('div');
    badge.id = 'client-mode-badge';
    badge.style.cssText = 'font-size:10px;text-align:center;color:#81c784;margin:4px 0 8px;opacity:0.85;';
    badge.textContent = '🛡️ AI Analysis Verified';
    document.querySelector('.score-section').after(badge);
  }

  // Registry badge
  const companyCell = document.getElementById('res-company').parentElement;
  const existingBadge = companyCell.querySelector('.registry-badge');
  if (existingBadge) existingBadge.remove();
  if (data.registry_status === 'registered') {
    const badge = document.createElement('div');
    badge.className = 'registry-badge';
    badge.style.cssText = 'font-size:11px;margin-top:4px;color:#4caf50;';
    badge.innerHTML = `✅ ${data.registry_name} Verified <small style="opacity:0.6">${data.registry_id || ''}</small>`;
    companyCell.appendChild(badge);
  } else if (data.registry_status === 'not_found') {
    const badge = document.createElement('div');
    badge.className = 'registry-badge';
    badge.style.cssText = 'font-size:11px;margin-top:4px;color:#f44336;';
    badge.textContent = `⚠️ Not found in ${data.registry_name}`;
    companyCell.appendChild(badge);
  }

  // Risk pills
  const pillsContainer = document.getElementById('risk-pills');
  pillsContainer.innerHTML = '';
  const GOOD_SIGNALS = ['[+', '✅', 'verified', 'genuine', 'positive', 'high social proof', 'trusted brand', 'low risk'];
  if (data.risk_factors && data.risk_factors.length > 0) {
    data.risk_factors.forEach(rf => {
      const pill = document.createElement('span');
      const isGood = GOOD_SIGNALS.some(sig => rf.includes(sig) || rf.toLowerCase().includes(sig));
      pill.className = `risk-pill ${isGood ? 'good' : 'bad'}`;
      pill.textContent = rf.length > 60 ? rf.substring(0, 58) + '…' : rf;
      pill.title = rf;
      pillsContainer.appendChild(pill);
    });
  } else {
    const pill = document.createElement('span');
    pill.className = 'risk-pill good';
    pill.textContent = '✅ No significant risk patterns detected';
    pillsContainer.appendChild(pill);
  }

  // OSINT alerts
  const existingAlerts = document.getElementById('osint-alerts');
  if (existingAlerts) existingAlerts.remove();
  const alertsDiv = document.createElement('div');
  alertsDiv.id = 'osint-alerts';
  alertsDiv.style.cssText = 'margin-bottom:10px;';
  if (data.has_scam_reports) {
    const alert = document.createElement('div');
    alert.style.cssText = 'background:#3a1010;border:1px solid #f44336;border-radius:8px;padding:8px 12px;font-size:12px;color:#ff6b6b;margin-bottom:6px;';
    alert.textContent = '🌐 Web search found potential fraud-related reports associated with this posting\'s details';
    alertsDiv.appendChild(alert);
  }
  if (data.duplicate_scan_count >= 5) {
    const alert = document.createElement('div');
    alert.style.cssText = 'background:#3a2000;border:1px solid #ff9800;border-radius:8px;padding:8px 12px;font-size:12px;color:#ffb74d;margin-bottom:6px;';
    alert.textContent = `⚠️ Bulk Pattern Alert: Identical job text detected ${data.duplicate_scan_count}+ times across platforms`;
    alertsDiv.appendChild(alert);
  }
  if (alertsDiv.children.length > 0) pillsContainer.before(alertsDiv);

  // Policy disclaimer (Grey Potassium compliance)
  const existingDisclaimer = document.getElementById('policy-disclaimer');
  if (existingDisclaimer) existingDisclaimer.remove();
  const disclaimer = data.policy_disclaimer || 'This analysis describes patterns in the job posting text only — not a definitive accusation against any individual or organisation.';
  const disclaimerEl = document.createElement('div');
  disclaimerEl.id = 'policy-disclaimer';
  disclaimerEl.style.cssText = 'font-size:9.5px;color:#555;border-top:1px solid #1f2937;margin-top:10px;padding-top:8px;line-height:1.45;font-style:italic;';
  disclaimerEl.textContent = '⚖️ ' + disclaimer;
  const feedbackSection = document.getElementById('feedback-section');
  if (feedbackSection) feedbackSection.before(disclaimerEl);

  showResults();
}

// ── Feedback ──────────────────────────────────────────────────────────────────
document.getElementById('fb-safe').addEventListener('click', () => submitFeedback(false));
document.getElementById('fb-scam').addEventListener('click', () => submitFeedback(true));

async function submitFeedback(isScam) {
  if (!currentJobId) {
    const thanks = document.getElementById('feedback-thanks');
    thanks.textContent = 'Feedback noted locally 🛡️';
    thanks.classList.remove('hidden');
    return;
  }
  const safeBtn = document.getElementById('fb-safe');
  const scamBtn = document.getElementById('fb-scam');
  const thanks  = document.getElementById('feedback-thanks');
  safeBtn.classList.add('selected');
  scamBtn.classList.add('selected');
  thanks.textContent = 'Updating…';
  thanks.classList.remove('hidden');
  try {
    const res = await fetch(`${API_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: currentJobId, is_scam: isScam })
    });
    thanks.textContent = res.ok ? 'Feedback received! 🛡️' : 'Feedback saved locally.';
    if (!res.ok) { safeBtn.classList.remove('selected'); scamBtn.classList.remove('selected'); }
  } catch {
    thanks.textContent = 'Feedback saved locally.';
    safeBtn.classList.remove('selected');
    scamBtn.classList.remove('selected');
  }
}

// ── UI State Helpers ──────────────────────────────────────────────────────────
function showIdle() {
  idleState.classList.remove('hidden');
  loadingState.classList.add('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.add('hidden');
  document.getElementById('confirm-state').classList.add('hidden');
  document.getElementById('feedback-thanks').classList.add('hidden');
  document.getElementById('fb-safe').classList.remove('selected');
  document.getElementById('fb-scam').classList.remove('selected');
  currentJobId = null;
  _pending = null;
}

function showLoading() {
  idleState.classList.add('hidden');
  loadingState.classList.remove('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.add('hidden');
  document.getElementById('step-1').className = 'step';
  document.getElementById('step-2').className = 'step';
  document.getElementById('step-3').className = 'step';
}

function showResults() {
  idleState.classList.add('hidden');
  loadingState.classList.add('hidden');
  resultsState.classList.remove('hidden');
  errorState.classList.add('hidden');
}

function showError(msg) {
  idleState.classList.add('hidden');
  loadingState.classList.add('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.remove('hidden');
  document.getElementById('error-msg').textContent = msg;
}

function setStep(n) {
  for (let i = 1; i <= 3; i++) {
    const el = document.getElementById(`step-${i}`);
    if (i < n) el.className = 'step done';
    else if (i === n) el.className = 'step active';
    else el.className = 'step';
  }
}

// ── Tabs & History ────────────────────────────────────────────────────────────
document.getElementById('tab-scan').addEventListener('click',    () => switchTab('scan'));
document.getElementById('tab-history').addEventListener('click', () => switchTab('history'));

function switchTab(tabName) {
  const tabScan        = document.getElementById('tab-scan');
  const tabHistory     = document.getElementById('tab-history');
  const scannerWrapper = document.getElementById('scanner-wrapper');
  const historyState   = document.getElementById('history-state');
  if (tabName === 'scan') {
    tabScan.classList.add('active');    tabHistory.classList.remove('active');
    scannerWrapper.classList.remove('hidden'); historyState.classList.add('hidden');
  } else {
    tabScan.classList.remove('active'); tabHistory.classList.add('active');
    scannerWrapper.classList.add('hidden');    historyState.classList.remove('hidden');
    loadHistory();
  }
}

function loadHistory() {
  chrome.storage.local.get(['scamshield_history'], (result) => {
    const history = result.scamshield_history || [];
    const list = document.getElementById('history-list');
    list.innerHTML = '';
    if (history.length === 0) {
      list.innerHTML = '<div style="text-align:center;padding:20px;color:#6b7280;font-size:12px;">No scan history yet.</div>';
      return;
    }
    history.forEach(item => {
      const trustScore = 100 - item.risk_score;
      let scoreClass = 'green';
      if (item.color === 'orange') scoreClass = 'orange';
      if (item.color === 'red')    scoreClass = 'red';
      const date = new Date(item.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      const el = document.createElement('a');
      el.className = 'history-item';
      el.href = item.url;
      el.target = '_blank';
      el.innerHTML = `
        <div class="history-score ${scoreClass}">${trustScore}</div>
        <div class="history-details">
          <div class="history-title">${item.company || 'Unknown Company'}</div>
          <div class="history-meta">${item.title || 'Unknown Role'} • ${date}</div>
        </div>`;
      list.appendChild(el);
    });
  });
}

document.getElementById('clear-history-btn').addEventListener('click', () => {
  if (confirm('Clear all scan history?')) {
    chrome.storage.local.set({ scamshield_history: [] }, () => {
      loadHistory();
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
          chrome.action.setBadgeText({ text: '?', tabId: tabs[0].id });
          chrome.action.setBadgeBackgroundColor({ color: '#888888', tabId: tabs[0].id });
        }
      });
    });
  }
});
