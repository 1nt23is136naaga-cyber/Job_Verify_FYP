// popup.js — ScamShield Extension v3.0

let API_URL = 'http://localhost:8000';
let currentJobId = null;
let currentSource = 'other';

// ── DOM Refs ──────────────────────────────────────────────────────────────────
const idleState     = document.getElementById('idle-state');
const loadingState  = document.getElementById('loading-state');
const resultsState  = document.getElementById('results-state');
const errorState    = document.getElementById('error-state');
const siteBadge     = document.getElementById('site-badge');
const statusDot     = document.getElementById('status-dot');
const settingsModal = document.getElementById('settings-modal');
const apiUrlInput   = document.getElementById('api-url-input');

// ── Helper: Ping API Health ───────────────────────────────────────────────────
async function checkApiHealth() {
  try {
    const r = await fetch(`${API_URL}/docs`, { method: 'HEAD' });
    if (r.ok || r.status === 200 || r.status === 404) {
      statusDot.className = 'status-dot';
      statusDot.title = `Connected to ${API_URL}`;
      return true;
    }
    throw new Error();
  } catch {
    statusDot.className = 'status-dot offline';
    statusDot.title = `API Offline — start server at ${API_URL}`;
    return false;
  }
}

// ── On Load: read stored API URL, detect site & ping API ───────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Read stored API URL if user customized it
  chrome.storage.local.get(['api_url'], async (res) => {
    if (res.api_url) {
      API_URL = res.api_url;
    }
    apiUrlInput.value = API_URL;
    await checkApiHealth();
  });

  // Detect active tab
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      const host = new URL(tab.url).hostname;
      if (host.includes('linkedin.com')) {
        siteBadge.textContent = '📋 LinkedIn — ready to analyze';
        currentSource = 'linkedin';
      } else if (host.includes('mail.google.com')) {
        siteBadge.textContent = '📧 Gmail — ready to analyze';
        currentSource = 'gmail';
      } else if (host.includes('internshala.com')) {
        siteBadge.textContent = '🎓 Internshala — ready to analyze';
        currentSource = 'internshala';
      } else if (host.includes('naukri.com')) {
        siteBadge.textContent = '💼 Naukri — ready to analyze';
        currentSource = 'naukri';
      } else {
        siteBadge.textContent = '🌐 ' + host + ' — use manual input below';
        currentSource = 'other';
      }
    }
  } catch(e) {}
});

// ── Settings Modal Handlers ───────────────────────────────────────────────────
document.getElementById('settings-btn').addEventListener('click', () => {
  settingsModal.classList.toggle('hidden');
});
document.getElementById('close-settings-btn').addEventListener('click', () => {
  settingsModal.classList.add('hidden');
});
document.getElementById('save-api-btn').addEventListener('click', async () => {
  const newUrl = (apiUrlInput.value.trim() || 'http://localhost:8000').replace(/\/+$/, '');
  API_URL = newUrl;
  chrome.storage.local.set({ api_url: newUrl }, async () => {
    const ok = await checkApiHealth();
    alert(ok ? `✅ Connected to ${newUrl}` : `⚠️ Saved, but could not reach ${newUrl}. Make sure the server is running.`);
    settingsModal.classList.add('hidden');
  });
});
document.getElementById('reset-api-btn').addEventListener('click', () => {
  API_URL = 'http://localhost:8000';
  apiUrlInput.value = API_URL;
  chrome.storage.local.remove(['api_url'], async () => {
    await checkApiHealth();
    settingsModal.classList.add('hidden');
  });
});

// Pending extraction data (held between scrape and confirm)
let _pending = null;

// ── Analyze from page ─────────────────────────────────────────────────────────
document.getElementById('analyze-btn').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  const btn = document.getElementById('analyze-btn');
  btn.disabled = true;
  btn.querySelector('span:last-child').textContent = 'Extracting…';

  chrome.tabs.sendMessage(tab.id, { action: 'extract_text' }, async (response) => {
    btn.disabled = false;
    btn.querySelector('span:last-child').textContent = 'Analyze Now';

    if (chrome.runtime.lastError || !response || !response.text || response.text.trim().length < 20) {
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
});

// ── Confirm state: user reviews scraped data ──────────────────────────────────
function showConfirm(pending) {
  const meta = pending.metadata || {};

  document.getElementById('confirm-company').value   = meta.company        || meta.title?.split('|')[1]?.trim() || '';
  document.getElementById('confirm-recruiter').value = meta.poster_name    || '';
  document.getElementById('confirm-title').value     = meta.title          || '';

  const bioRow = document.getElementById('confirm-bio-row');
  const bioEl  = document.getElementById('confirm-bio');
  if (meta.poster_headline) {
    bioEl.textContent = meta.poster_headline;
    bioRow.style.display = 'flex';
  } else {
    bioRow.style.display = 'none';
  }

  document.getElementById('confirm-text-preview').textContent =
    pending.text.trim().slice(0, 250) + (pending.text.length > 250 ? '…' : '');

  const imgRow = document.getElementById('confirm-images-row');
  if (pending.imageData.length > 0 || pending.imageUrls.length > 0) {
    const total = Math.max(pending.imageData.length, pending.imageUrls.length);
    document.getElementById('confirm-images-count').textContent =
      `${total} image(s) captured — will be OCR'd by Gemini Vision ✅`;
    imgRow.style.display = 'flex';
  } else {
    imgRow.style.display = 'none';
  }

  idleState.classList.add('hidden');
  loadingState.classList.add('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.add('hidden');
  document.getElementById('confirm-state').classList.remove('hidden');
}

// Confirm & Analyze
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

// Back to idle
document.getElementById('confirm-back-btn').addEventListener('click', () => {
  document.getElementById('confirm-state').classList.add('hidden');
  showIdle();
});

// ── Analyze from manual textarea ─────────────────────────────────────────────
document.getElementById('manual-btn').addEventListener('click', async () => {
  const text = document.getElementById('manual-text').value.trim();
  if (text.length < 20) {
    alert('Please paste at least a short job description.');
    return;
  }
  showLoading();
  setStep(1);
  await runAnalysis(text, {});
});

// ── Re-analyze ────────────────────────────────────────────────────────────────
document.getElementById('reanalyze-btn').addEventListener('click', () => {
  showIdle();
});
document.getElementById('retry-btn').addEventListener('click', () => {
  showIdle();
});

// ── Full Scan (analyze + deep scraper → one final result) ────────────────────
const PHASE_LABELS = {
  starting:      '⚙️ Starting scan…',
  analyzing:     '🔍 Analyzing job text, company & recruiter…',
  deep_scanning: '🌐 Deep verifying across 14 platforms (Naukri, Indeed, LinkedIn…)',
  done:          '✅ Done!'
};

async function runAnalysis(text, metadata, imageData = []) {
  showLoading();
  setStep(1);

  try {
    const startRes = await fetch(`${API_URL}/full_scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source: currentSource, metadata, image_data: imageData })
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
        if (attempts > 60) {
          clearInterval(poller);
          reject(new Error('Scan timed out after 5 minutes.'));
          return;
        }
        try {
          const poll = await fetch(`${API_URL}/full_scan_status/${scan_id}`);
          const result = await poll.json();

          if (loadingMsg && PHASE_LABELS[result.phase]) {
            loadingMsg.textContent = PHASE_LABELS[result.phase];
          }

          if (result.status === 'done') {
            clearInterval(poller);
            data = result;
            resolve();
          }
        } catch(e) {}
      }, 3500);
    });

    setStep(3);
    currentJobId = data.job_id;

    const resolvedCompany = (data.company && data.company !== 'Unknown') ? data.company : (_pending?.metadata?.company || 'Unknown Company');
    const resolvedTitle   = (data.job_title && data.job_title !== 'Not detected' && data.job_title !== 'Unknown') ? data.job_title : (_pending?.metadata?.title || 'Unknown Role');
    const resolvedRecruiter = (data.recruiter && data.recruiter !== 'Unknown') ? data.recruiter : (_pending?.metadata?.poster_name || 'Not listed');

    // Save to history
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      chrome.storage.local.get(['scamshield_history'], (result) => {
        let history = result.scamshield_history || [];
        history = history.filter(h => h.url !== tab.url.split('?')[0]);
        history.unshift({
          url: tab.url.split('?')[0],
          company: resolvedCompany,
          title: resolvedTitle,
          risk_score: data.risk_score,
          color: data.color,
          verdict: data.verdict,
          timestamp: new Date().toISOString()
        });
        history = history.slice(0, 50);
        chrome.storage.local.set({ scamshield_history: history }, () => {
          chrome.action.setBadgeText({ text: (100 - data.risk_score).toString(), tabId: tab.id });
          let badgeColor = '#4caf50';
          if (data.color === 'orange') badgeColor = '#ff9800';
          if (data.color === 'red')    badgeColor = '#f44336';
          chrome.action.setBadgeBackgroundColor({ color: badgeColor, tabId: tab.id });
          chrome.tabs.sendMessage(tab.id, { action: 'update_badges' });
        });
      });
    }

    const dvBanner = document.getElementById('deep-verify-banner');
    if (dvBanner) dvBanner.style.display = 'none';

    renderResults(data);

    const dv = data.deep_verify;
    if (dv && dvBanner) {
      const colorMap = { green: '#2e7d32', orange: '#e65100', red: '#b71c1c' };
      dvBanner.style.display   = 'block';
      dvBanner.style.background = colorMap[data.color] || '#1e3a5f';
      dvBanner.style.color     = '#fff';
      const hits      = dv.portal_hits ?? 0;
      const confirmed = dv.confirmed_on?.join(', ') || 'None';
      const notFound  = dv.not_found_on?.join(', ')  || 'None';
      dvBanner.innerHTML =
        `<strong>🔍 Deep Verify: ${dv.verdict || 'N/A'}</strong><br>` +
        `✅ Found on (${hits}): ${confirmed}<br>` +
        `❌ Not found: ${notFound}` +
        (dv.careers_url ? `<br>🏢 <a href="${dv.careers_url}" target="_blank" style="color:#90caf9">${dv.careers_url}</a>` : '') +
        (dv.time_taken  ? `<br><small style="opacity:0.7">⏱ ${Number(dv.time_taken).toFixed(1)}s</small>` : '');
    }

  } catch (err) {
    showError(`Failed to connect to the backend (${API_URL}).\n\nMake sure the server is running:\n→ python api.py\n\n${err.message}`);
  }
}

// ── Render Results ────────────────────────────────────────────────────────────
function renderResults(data) {
  const riskScore = data.risk_score ?? 0;
  const trustScore = 100 - riskScore;

  const circumference = 314;
  const offset = circumference - (trustScore / 100) * circumference;
  const ring = document.getElementById('ring-fill');
  ring.style.strokeDashoffset = offset;

  const numEl = document.getElementById('score-number');
  let count = 0;
  const target = trustScore;
  const interval = setInterval(() => {
    count = Math.min(count + 2, target);
    numEl.textContent = count;
    if (count >= target) clearInterval(interval);
  }, 20);

  const verdictEl = document.getElementById('verdict-text');
  const subEl = document.getElementById('verdict-sub');
  verdictEl.textContent = data.verdict || '—';

  const scoreSection = document.querySelector('.score-section');
  scoreSection.classList.remove('verdict-green','verdict-orange','verdict-red');
  if (data.color === 'green') {
    scoreSection.classList.add('verdict-green');
    subEl.textContent = 'No major red flags detected';
  } else if (data.color === 'orange') {
    scoreSection.classList.add('verdict-orange');
    subEl.textContent = 'Some signals need attention — verify before applying';
  } else {
    scoreSection.classList.add('verdict-red');
    subEl.textContent = 'Multiple risk signals detected — proceed with caution';
  }

  const resCompany = (data.company && data.company !== 'Unknown') ? data.company : (_pending?.metadata?.company || 'Unknown');
  const resTitle   = (data.job_title && data.job_title !== 'Not detected' && data.job_title !== 'Unknown') ? data.job_title : (_pending?.metadata?.title || 'Not detected');
  const resRec     = (data.recruiter && data.recruiter !== 'Unknown') ? data.recruiter : (_pending?.metadata?.poster_name || 'Not listed');

  document.getElementById('res-company').textContent   = resCompany;
  document.getElementById('res-recruiter').textContent = resRec;
  document.getElementById('res-email').textContent     = data.email      || 'Not found';
  document.getElementById('res-title').textContent     = resTitle;
  
  const bertCard = document.getElementById('bert-card');
  if (data.bert_probability !== undefined && data.bert_probability !== null) {
    bertCard.style.display = 'block';
    const bertPct = Math.round(data.bert_probability * 100);
    const bertText = bertPct > 60 ? `🚨 ${bertPct}% Scam Probability` : `✅ ${bertPct}% Scam Probability`;
    document.getElementById('res-bert').textContent = bertText;
    document.getElementById('res-bert').style.color = bertPct > 60 ? '#fca5a5' : '#86efac';
  } else {
    bertCard.style.display = 'none';
  }
  
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
    badge.textContent = `⚠️ Not in ${data.registry_name}`;
    companyCell.appendChild(badge);
  }

  const pillsContainer = document.getElementById('risk-pills');
  pillsContainer.innerHTML = '';
  const GOOD_SIGNALS = ['[+', '✅', 'verified', 'genuine', 'positive', 'high social proof', 'trusted brand'];
  if (data.risk_factors && data.risk_factors.length > 0) {
    data.risk_factors.forEach(rf => {
      const pill = document.createElement('span');
      const rfLower = rf.toLowerCase();
      const isGood = GOOD_SIGNALS.some(sig => rf.includes(sig) || rfLower.includes(sig));
      pill.className = `risk-pill ${isGood ? 'good' : 'bad'}`;
      pill.textContent = rf.length > 60 ? rf.substring(0, 58) + '…' : rf;
      pill.title = rf;
      pillsContainer.appendChild(pill);
    });
  } else {
    const pill = document.createElement('span');
    pill.className = 'risk-pill good';
    pill.textContent = '✅ All checks passed clean';
    pillsContainer.appendChild(pill);
  }

  const existingAlerts = document.getElementById('osint-alerts');
  if (existingAlerts) existingAlerts.remove();
  
  const alertsDiv = document.createElement('div');
  alertsDiv.id = 'osint-alerts';
  alertsDiv.style.cssText = 'margin-bottom:10px;';
  
  if (data.has_scam_reports) {
    const alert = document.createElement('div');
    alert.style.cssText = 'background:#3a1010;border:1px solid #f44336;border-radius:8px;padding:8px 12px;font-size:12px;color:#ff6b6b;margin-bottom:6px;';
    alert.textContent = '🌐 Web OSINT: Scam/fraud reports found for this company online';
    alertsDiv.appendChild(alert);
  }
  if (data.duplicate_scan_count >= 5) {
    const alert = document.createElement('div');
    alert.style.cssText = 'background:#3a2000;border:1px solid #ff9800;border-radius:8px;padding:8px 12px;font-size:12px;color:#ffb74d;margin-bottom:6px;';
    alert.textContent = `🚨 Bulk Spam Alert: This exact job text has been scanned ${data.duplicate_scan_count} times`;
    alertsDiv.appendChild(alert);
  }
  if (alertsDiv.children.length > 0) {
    const pillsContainer = document.getElementById('risk-pills');
    pillsContainer.before(alertsDiv);
  }

  showResults();
}

// ── Feedback Handlers ───────────────────────────────────────────────────────
document.getElementById('fb-safe').addEventListener('click', () => submitFeedback(false));
document.getElementById('fb-scam').addEventListener('click', () => submitFeedback(true));

async function submitFeedback(isScam) {
  if (!currentJobId) {
    console.warn('Feedback clicked but no Job ID available');
    return;
  }
  
  const safeBtn = document.getElementById('fb-safe');
  const scamBtn = document.getElementById('fb-scam');
  const thanks = document.getElementById('feedback-thanks');
  
  safeBtn.classList.add('selected');
  scamBtn.classList.add('selected');
  thanks.textContent = 'Updating...';
  thanks.classList.remove('hidden');

  try {
    const res = await fetch(`${API_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: currentJobId, is_scam: isScam })
    });
    if (res.ok) {
      thanks.textContent = 'Feedback received! 🛡️';
    } else {
      throw new Error(`Server returned ${res.status}`);
    }
  } catch (err) {
    thanks.textContent = 'Failed to save feedback.';
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
document.getElementById('tab-scan').addEventListener('click', () => switchTab('scan'));
document.getElementById('tab-history').addEventListener('click', () => switchTab('history'));

function switchTab(tabName) {
  const tabScan = document.getElementById('tab-scan');
  const tabHistory = document.getElementById('tab-history');
  const scannerWrapper = document.getElementById('scanner-wrapper');
  const historyState = document.getElementById('history-state');

  if (tabName === 'scan') {
    tabScan.classList.add('active');
    tabHistory.classList.remove('active');
    scannerWrapper.classList.remove('hidden');
    historyState.classList.add('hidden');
  } else {
    tabScan.classList.remove('active');
    tabHistory.classList.add('active');
    scannerWrapper.classList.add('hidden');
    historyState.classList.remove('hidden');
    loadHistory();
  }
}

function loadHistory() {
  chrome.storage.local.get(['scamshield_history'], (result) => {
    const history = result.scamshield_history || [];
    const list = document.getElementById('history-list');
    list.innerHTML = '';
    
    if (history.length === 0) {
      list.innerHTML = '<div style="text-align:center; padding:20px; color:#6b7280; font-size:12px;">No scan history yet.</div>';
      return;
    }
    
    history.forEach(item => {
      const trustScore = 100 - item.risk_score;
      let scoreClass = 'green';
      if (item.color === 'orange') scoreClass = 'orange';
      if (item.color === 'red') scoreClass = 'red';
      
      const date = new Date(item.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute:'2-digit' });
      
      const el = document.createElement('a');
      el.className = 'history-item';
      el.href = item.url;
      el.target = '_blank';
      el.innerHTML = `
        <div class="history-score ${scoreClass}">${trustScore}</div>
        <div class="history-details">
          <div class="history-title">${item.company || 'Unknown Company'}</div>
          <div class="history-meta">${item.title || 'Unknown Role'} • ${date}</div>
        </div>
      `;
      list.appendChild(el);
    });
  });
}

document.getElementById('clear-history-btn').addEventListener('click', () => {
  if(confirm("Clear all scan history?")) {
    chrome.storage.local.set({ scamshield_history: [] }, () => {
      loadHistory();
      chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        if(tabs[0]) {
          chrome.action.setBadgeText({ text: '?', tabId: tabs[0].id });
          chrome.action.setBadgeBackgroundColor({ color: '#888888', tabId: tabs[0].id });
        }
      });
    });
  }
});
