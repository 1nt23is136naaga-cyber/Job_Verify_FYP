// popup.js — ScamShield Extension

const API_URL = 'http://localhost:8000';
let currentJobId = null;
let currentSource = 'other';

// ── DOM Refs ──────────────────────────────────────────────────────────────────
const idleState     = document.getElementById('idle-state');
const loadingState  = document.getElementById('loading-state');
const resultsState  = document.getElementById('results-state');
const errorState    = document.getElementById('error-state');
const siteBadge     = document.getElementById('site-badge');
const statusDot     = document.getElementById('status-dot');

// ── On Load: detect site & ping API ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Check API health
  try {
    const r = await fetch(`${API_URL}/docs`, { method: 'HEAD' });
    if (!r.ok) throw new Error();
  } catch {
    statusDot.classList.add('offline');
    statusDot.title = 'API Offline — start server';
  }

  // Detect active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
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
});

// ── Analyze from page ─────────────────────────────────────────────────────────
document.getElementById('analyze-btn').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  showLoading();

  setStep(1);
  chrome.tabs.sendMessage(tab.id, { action: 'extract_text' }, async (response) => {
    if (chrome.runtime.lastError || !response || !response.text || response.text.trim().length < 20) {
      showError('Could not extract text from this page.\n\nTry using the manual paste box below.');
      return;
    }
    setStep(2);
    await runAnalysis(response.text, response.metadata || {}, response.image_data || []);
  });
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

// ── Core Analysis Call ────────────────────────────────────────────────────────
async function runAnalysis(text, metadata, imageData = []) {
  setStep(2);
  try {
    console.log('Sending Analysis Request:', { source: currentSource, metadata, images: imageData.length });
    const res = await fetch(`${API_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source: currentSource, metadata: metadata, image_data: imageData })
    });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    setStep(3);
    const data = await res.json();
    currentJobId = data.job_id;
    
    // Save to history for background/content scripts
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      chrome.storage.local.get(['scamshield_history'], (result) => {
        let history = result.scamshield_history || [];
        const currentUrl = tab.url.split('?')[0];
        
        // Remove existing entry for this URL if present
        history = history.filter(h => h.url !== currentUrl);
        
        // Add new entry
        history.unshift({
          url: currentUrl,
          company: data.company,
          title: data.job_title,
          risk_score: data.risk_score,
          color: data.color,
          verdict: data.verdict,
          timestamp: new Date().toISOString()
        });
        
        // Keep only last 50
        history = history.slice(0, 50);
        
        chrome.storage.local.set({ scamshield_history: history }, () => {
          // Trigger the background script to update the badge immediately
          chrome.action.setBadgeText({ text: (100 - data.risk_score).toString(), tabId: tab.id });
          let badgeColor = '#4caf50'; // Green
          if (data.color === 'orange') badgeColor = '#ff9800';
          if (data.color === 'red') badgeColor = '#f44336';
          chrome.action.setBadgeBackgroundColor({ color: badgeColor, tabId: tab.id });
          
          // Trigger content script to update job card badges if on list view
          chrome.tabs.sendMessage(tab.id, { action: 'update_badges' });
        });
      });
    }
    
    renderResults(data);
  } catch (err) {
    showError(`Failed to connect to the backend.\n\nMake sure the server is running:\n→ python -m uvicorn api:app --port 8000\n\n${err.message}`);
  }
}

// ── Render Results ────────────────────────────────────────────────────────────
function renderResults(data) {
  // Convert backend risk_score to a display Trust Score
  // risk_score: 0 = safe, 100 = scam
  // trust_score: 100 = safe, 0 = scam  (inverted for intuitive UI)
  const riskScore = data.risk_score ?? 0;
  const trustScore = 100 - riskScore;

  // Score ring animation — fill based on trust score (high fill = safe)
  const circumference = 314;
  const offset = circumference - (trustScore / 100) * circumference;
  const ring = document.getElementById('ring-fill');
  ring.style.strokeDashoffset = offset;

  // Score number count-up to trust score
  const numEl = document.getElementById('score-number');
  let count = 0;
  const target = trustScore;
  const interval = setInterval(() => {
    count = Math.min(count + 2, target);
    numEl.textContent = count;
    if (count >= target) clearInterval(interval);
  }, 20);

  // Verdict
  const verdictEl = document.getElementById('verdict-text');
  const subEl = document.getElementById('verdict-sub');
  verdictEl.textContent = data.verdict || '—';

  // Color class on score section
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

  // Info grid
  document.getElementById('res-company').textContent   = data.company   || 'Unknown';
  document.getElementById('res-recruiter').textContent = data.recruiter  || 'Unknown';
  document.getElementById('res-email').textContent     = data.email      || 'Not found';
  
  // Always show job title
  document.getElementById('res-title').textContent = data.job_title || 'Not detected';
  
  // Dynamic Registry Badge — shown below the Company name (not title)
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

  // Risk pills
  const pillsContainer = document.getElementById('risk-pills');
  pillsContainer.innerHTML = '';
  const GOOD_SIGNALS = ['[+', '✅', 'verified', 'genuine', 'positive', 'high social proof', 'trusted brand'];
  if (data.risk_factors && data.risk_factors.length > 0) {
    data.risk_factors.forEach(rf => {
      const pill = document.createElement('span');
      const rfLower = rf.toLowerCase();
      const isGood = GOOD_SIGNALS.some(sig => rf.includes(sig) || rfLower.includes(sig));
      pill.className = `risk-pill ${isGood ? 'good' : 'bad'}`;
      // Shorten for display
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

  // OSINT Alerts — shown as inline banners if triggered
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
  
  // Visual state
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
      console.log('Feedback saved successfully');
    } else {
      throw new Error(`Server returned ${res.status}`);
    }
  } catch (err) {
    console.error('Feedback error:', err);
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
  document.getElementById('feedback-thanks').classList.add('hidden');
  document.getElementById('fb-safe').classList.remove('selected');
  document.getElementById('fb-scam').classList.remove('selected');
  currentJobId = null;
}

function showLoading() {
  idleState.classList.add('hidden');
  loadingState.classList.remove('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.add('hidden');
  // Reset steps
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
      
      // Clear badges from active tab
      chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        if(tabs[0]) {
          chrome.action.setBadgeText({ text: '?', tabId: tabs[0].id });
          chrome.action.setBadgeBackgroundColor({ color: '#888888', tabId: tabs[0].id });
        }
      });
    });
  }
});
