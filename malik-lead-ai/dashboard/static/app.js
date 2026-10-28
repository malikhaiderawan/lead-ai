/**
 * MalikAxiom Lead AI — M7 Sales Command Center Frontend Engine
 * Zero external JS dependencies. Pure modern ECMAScript.
 */

// Application State
const State = {
  currentView: 'dashboard',
  dateFilter: 'ALL_TIME',
  customStart: '',
  customEnd: '',
  searchQuery: '',
  leadsPage: 1,
  leadsLimit: 50,
  leadsTotalPages: 1,
  leadsTab: 'WATCHES',
  activeLeadId: null,
  cachedLead: null,
  refreshing: false,
  pollInterval: null,
  leadsFilter: {
    niche: 'WATCHES',
    country: '',
    priority: '',
    potential: '',
    channel: '',
    status: '',
    milestone: '',
    city: '',
    call_status: '',
    category: '',
    activity: '',
    sort_by: '',
  },
  crmMetrics: null,
  waFilter: {
    status: '',
    search: '',
    city: '',
  },
  coldCallingFilter: {
    tab: 'ALL',
    call_status: '',
    search: '',
    priority: '',
    potential: '',
    city: '',
  },
  igFilter: {
    search: '',
    potential: '',
    city: '',
  }
};

// DOM Content Loaded Initializer
document.addEventListener('DOMContentLoaded', () => {
  initThemeEngine();
  initNavigation();
  initDateFilters();
  initSearch();
  initTableFilters();
  initModals();
  initAutoRefresh();
  startSidebarClock();

  // Initial load
  refreshAll();
});

/* --------------------------------------------------------------------------
   Theme Switcher Engine (Light / Dark Mode)
   -------------------------------------------------------------------------- */

function initThemeEngine() {
  const savedTheme = localStorage.getItem('malikaxiom_dashboard_theme') || 'light';
  applyTheme(savedTheme);
}

function toggleDashboardTheme() {
  const currentTheme = document.body.classList.contains('dark-theme') ? 'dark' : 'light';
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
  localStorage.setItem('malikaxiom_dashboard_theme', newTheme);
}

function applyTheme(theme) {
  const iconSpan = document.getElementById('theme-toggle-icon');
  const labelSpan = document.getElementById('theme-toggle-label');
  if (theme === 'dark') {
    document.body.classList.remove('light-theme');
    document.body.classList.add('dark-theme');
    if (iconSpan) iconSpan.textContent = '🌙';
    if (labelSpan) labelSpan.textContent = 'Dark Mode';
  } else {
    document.body.classList.remove('dark-theme');
    document.body.classList.add('light-theme');
    if (iconSpan) iconSpan.textContent = '☀️';
    if (labelSpan) labelSpan.textContent = 'Light Mode';
  }
}

/* --------------------------------------------------------------------------
   Navigation & Routing
   -------------------------------------------------------------------------- */

function initNavigation() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      const view = item.getAttribute('data-view');
      const href = item.getAttribute('href');

      // If item has an href and no data-view (e.g. Demo 1 & Demo 2 links), allow standard browser navigation
      if (href && !view) {
        return;
      }

      e.preventDefault();
      if (view) {
        switchView(view);
      }
    });
  });
}

function switchView(viewName, filterOverrides = {}) {
  if (viewName === 'crm') {
    switchView('leads');
    return;
  }
  State.currentView = viewName;

  // Update sidebar active link
  document.querySelectorAll('.nav-item').forEach(item => {
    if (item.getAttribute('data-view') === viewName) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // Hide all view panes
  document.querySelectorAll('.view-pane').forEach(pane => {
    pane.style.display = 'none';
  });

  // Show target view pane
  const targetPane = document.getElementById(`view-${viewName}`);
  if (targetPane) {
    targetPane.style.display = 'block';
  }

  // Apply tab filter override if provided
  if (filterOverrides.tab !== undefined) {
    State.leadsTab = filterOverrides.tab;
    document.querySelectorAll('.leads-tabs-bar .tab-btn').forEach(btn => {
      if (btn.getAttribute('data-tab') === filterOverrides.tab) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  // Apply filter overrides if provided
  if (filterOverrides.priority !== undefined) {
    const sel = document.getElementById('filter-lead-priority');
    if (sel) sel.value = filterOverrides.priority;
    State.leadsFilter.priority = filterOverrides.priority;
  }
  if (filterOverrides.potential !== undefined) {
    const sel = document.getElementById('filter-lead-potential');
    if (sel) sel.value = filterOverrides.potential;
    State.leadsFilter.potential = filterOverrides.potential;
  }
  if (filterOverrides.status !== undefined) {
    const sel = document.getElementById('filter-wa-status');
    if (sel) sel.value = filterOverrides.status;
    State.waFilter.status = filterOverrides.status;
  }

  // Load view-specific data
  loadViewData(viewName);
}

function loadViewData(viewName) {
  switch (viewName) {
    case 'dashboard':
      fetchOverview();
      break;
    case 'activity':
      fetchActivity();
      break;
    case 'pipeline':
      fetchPipeline();
      break;
    case 'leads':
      fetchMasterLeads();
      break;
    case 'whatsapp':
      fetchWhatsApp();
      break;
    case 'cold-calling':
      fetchColdCalling();
      break;
    case 'instagram':
      fetchInstagram();
      break;
    case 'm2':
      fetchMilestoneM2();
      break;
    case 'm3':
      fetchMilestoneM3();
      break;
    case 'm4':
      fetchMilestoneM4();
      break;
    case 'm5':
      fetchMilestoneM5();
      break;
    case 'attention':
      fetchAttention();
      break;
    case 'analytics':
      fetchAnalytics();
      break;
    case 'sources':
      fetchSources();
      break;
  }
}

/* --------------------------------------------------------------------------
   Date Filtering & Search Controls
   -------------------------------------------------------------------------- */

function setGlobalDateFilter(val, specificDate = '') {
  State.dateFilter = val;
  State.leadsPage = 1;

  const dateSelect = document.getElementById('global-date-filter');
  const tableDateSelect = document.getElementById('filter-lead-date');
  const ccDateSelect = document.getElementById('filter-cc-date');
  const specificContainer = document.getElementById('specific-date-container');
  const customContainer = document.getElementById('custom-date-container');
  const specificInput = document.getElementById('specific-date-input');

  if (dateSelect) dateSelect.value = val;
  if (tableDateSelect) tableDateSelect.value = val;
  if (ccDateSelect && ['ALL_TIME', 'TODAY', 'YESTERDAY', 'PARSO', 'SPECIFIC_DATE', 'PAST_7_DAYS'].includes(val)) {
    ccDateSelect.value = val;
  }

  if (val === 'SPECIFIC_DATE') {
    if (specificContainer) specificContainer.style.display = 'flex';
    if (customContainer) customContainer.style.display = 'none';
    if (specificDate) {
      State.customStart = specificDate;
      State.customEnd = specificDate;
      if (specificInput) specificInput.value = specificDate;
      refreshAll();
    } else if (specificInput && specificInput.value) {
      State.customStart = specificInput.value;
      State.customEnd = specificInput.value;
      refreshAll();
    } else {
      // Focus on the date picker if empty
      if (specificInput) specificInput.focus();
    }
  } else if (val === 'CUSTOM') {
    if (specificContainer) specificContainer.style.display = 'none';
    if (customContainer) customContainer.style.display = 'flex';
  } else {
    if (specificContainer) specificContainer.style.display = 'none';
    if (customContainer) customContainer.style.display = 'none';
    State.customStart = '';
    State.customEnd = '';
    refreshAll();
  }
}

function initDateFilters() {
  const dateSelect = document.getElementById('global-date-filter');
  const tableDateSelect = document.getElementById('filter-lead-date');
  const ccDateSelect = document.getElementById('filter-cc-date');
  const btnApplySpecific = document.getElementById('btn-apply-specific-date');
  const specificInput = document.getElementById('specific-date-input');
  const btnApplyCustom = document.getElementById('btn-apply-custom-date');

  // Set default date input value to yesterday (when most recent leads were added) if not set
  if (specificInput && !specificInput.value) {
    specificInput.value = '2026-10-21';
  }

  if (dateSelect) {
    dateSelect.addEventListener('change', () => {
      setGlobalDateFilter(dateSelect.value);
    });
  }

  if (tableDateSelect) {
    tableDateSelect.addEventListener('change', () => {
      setGlobalDateFilter(tableDateSelect.value);
    });
  }

  if (ccDateSelect) {
    ccDateSelect.addEventListener('change', () => {
      setGlobalDateFilter(ccDateSelect.value);
    });
  }

  if (btnApplySpecific && specificInput) {
    btnApplySpecific.addEventListener('click', () => {
      const val = specificInput.value;
      if (val) {
        State.dateFilter = 'SPECIFIC_DATE';
        State.customStart = val;
        State.customEnd = val;
        State.leadsPage = 1;
        refreshAll();
        showToast(`Showing leads for ${val}`, 'info');
      } else {
        showToast('Please select a specific date', 'warning');
      }
    });

    specificInput.addEventListener('change', () => {
      if (specificInput.value) {
        State.dateFilter = 'SPECIFIC_DATE';
        State.customStart = specificInput.value;
        State.customEnd = specificInput.value;
        State.leadsPage = 1;
        refreshAll();
        showToast(`Showing leads for ${specificInput.value}`, 'info');
      }
    });
  }

  if (btnApplyCustom) {
    btnApplyCustom.addEventListener('click', () => {
      const startVal = document.getElementById('custom-date-start').value;
      const endVal = document.getElementById('custom-date-end').value;
      if (startVal && endVal) {
        State.dateFilter = 'CUSTOM';
        State.customStart = startVal;
        State.customEnd = endVal;
        State.leadsPage = 1;
        refreshAll();
        showToast(`Showing leads from ${startVal} to ${endVal}`, 'info');
      } else if (startVal) {
        State.dateFilter = 'SPECIFIC_DATE';
        State.customStart = startVal;
        State.customEnd = startVal;
        State.leadsPage = 1;
        refreshAll();
        showToast(`Showing leads for ${startVal}`, 'info');
      } else {
        showToast('Please select dates to filter', 'warning');
      }
    });
  }
}

function resetDateFilterToAllTime() {
  const dateSelect = document.getElementById('global-date-filter');
  const tableDateSelect = document.getElementById('filter-lead-date');
  const ccDateSelect = document.getElementById('filter-cc-date');
  const specificContainer = document.getElementById('specific-date-container');
  const customContainer = document.getElementById('custom-date-container');

  if (dateSelect) dateSelect.value = 'ALL_TIME';
  if (tableDateSelect) tableDateSelect.value = 'ALL_TIME';
  if (ccDateSelect) ccDateSelect.value = 'ALL_TIME';
  if (specificContainer) specificContainer.style.display = 'none';
  if (customContainer) customContainer.style.display = 'none';

  State.dateFilter = 'ALL_TIME';
  State.customStart = '';
  State.customEnd = '';
  State.leadsPage = 1;
  refreshAll();
  showToast('Reset to All Time (Showing all leads)', 'info');
}

function initSearch() {
  const searchInput = document.getElementById('global-search');
  let debounceTimeout = null;

  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
      State.searchQuery = searchInput.value.trim();
      State.leadsPage = 1;
      loadViewData(State.currentView);
    }, 250);
  });

  const btnRefresh = document.getElementById('btn-refresh');
  btnRefresh.addEventListener('click', () => {
    triggerManualRefresh();
  });
}

function initTableFilters() {
  // Tab filter listeners
  document.querySelectorAll('#leads-tabs-bar .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#leads-tabs-bar .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      State.leadsTab = btn.getAttribute('data-tab');
      State.leadsPage = 1;
      fetchMasterLeads();
    });
  });

  // Master leads filter listeners
  ['niche', 'country', 'city', 'priority', 'potential', 'channel', 'status', 'milestone', 'call-status', 'category', 'activity', 'sort'].forEach(filterKey => {
    let id = `filter-lead-${filterKey}`;
    if (filterKey === 'status') id = 'filter-lead-m6-status';
    const stateKey = filterKey === 'sort' ? 'sort_by' : filterKey.replace('-', '_');
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => {
        State.leadsFilter[stateKey] = el.value;
        State.leadsPage = 1;
        fetchMasterLeads();
      });
    }
  });

  // Reset Master Leads filter button
  const btnResetLeads = document.getElementById('btn-reset-lead-filters');
  if (btnResetLeads) {
    btnResetLeads.addEventListener('click', () => {
      State.leadsTab = 'ALL';
      State.leadsFilter = {
        priority: '',
        potential: '',
        channel: '',
        status: '',
        milestone: '',
        city: '',
        call_status: '',
        category: '',
        activity: '',
        sort_by: '',
      };
      document.querySelectorAll('.leads-tabs-bar .tab-btn').forEach(b => {
        if (b.getAttribute('data-tab') === 'ALL') b.classList.add('active');
        else b.classList.remove('active');
      });
      ['niche', 'country', 'city', 'priority', 'potential', 'channel', 'call-status', 'category', 'activity', 'sort'].forEach(k => {
        const el = document.getElementById(`filter-lead-${k}`);
        if (el) el.value = (k === 'niche' ? 'WATCHES' : '');
      });
      const stEl = document.getElementById('filter-lead-m6-status');
      if (stEl) stEl.value = '';
      const msEl = document.getElementById('filter-lead-milestone');
      if (msEl) msEl.value = '';
      State.leadsPage = 1;
      fetchMasterLeads();
    });
  }

  // WhatsApp filter listeners
  const waSearchInput = document.getElementById('filter-wa-search');
  if (waSearchInput) {
    let waDebounce = null;
    waSearchInput.addEventListener('input', () => {
      clearTimeout(waDebounce);
      waDebounce = setTimeout(() => {
        State.waFilter.search = waSearchInput.value.trim();
        fetchWhatsApp();
      }, 250);
    });
  }

  const waFilterSel = document.getElementById('filter-wa-status');
  if (waFilterSel) {
    waFilterSel.addEventListener('change', () => {
      State.waFilter.status = waFilterSel.value;
      fetchWhatsApp();
    });
  }

  const waCitySel = document.getElementById('filter-wa-city');
  if (waCitySel) {
    waCitySel.addEventListener('change', () => {
      State.waFilter.city = waCitySel.value;
      fetchWhatsApp();
    });
  }

  const btnResetWa = document.getElementById('btn-reset-wa-filters');
  if (btnResetWa) {
    btnResetWa.addEventListener('click', () => {
      State.waFilter = { status: '', search: '', city: '' };
      if (waSearchInput) waSearchInput.value = '';
      if (waFilterSel) waFilterSel.value = '';
      if (waCitySel) waCitySel.value = '';
      fetchWhatsApp();
    });
  }

  // Cold Calling Call Status tab listeners (Pending, Connected, Not Connected, All)
  document.querySelectorAll('#cold-calling-tabs-bar button[data-call-status]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#cold-calling-tabs-bar button[data-call-status]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const val = btn.getAttribute('data-call-status') || 'ALL';
      State.coldCallingFilter.call_status = val === 'ALL' ? '' : val;
      const ccStatusSelect = document.getElementById('filter-cold-calling-status');
      if (ccStatusSelect) ccStatusSelect.value = State.coldCallingFilter.call_status;
      fetchColdCalling();
    });
  });

  // Cold Calling Priority tab listeners (All, Contact First, Contact Later)
  document.querySelectorAll('#cold-calling-tabs-bar button[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#cold-calling-tabs-bar button[data-tab]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      State.coldCallingFilter.tab = btn.getAttribute('data-tab') || 'ALL';
      fetchColdCalling();
    });
  });

  // Cold Calling filter listeners
  const ccStatusSelect = document.getElementById('filter-cold-calling-status');
  if (ccStatusSelect) {
    ccStatusSelect.addEventListener('change', () => {
      const val = ccStatusSelect.value;
      State.coldCallingFilter.call_status = val;
      document.querySelectorAll('#cold-calling-tabs-bar button[data-call-status]').forEach(b => {
        const btnVal = b.getAttribute('data-call-status');
        if ((!val && btnVal === 'ALL') || btnVal === val) {
          b.classList.add('active');
        } else {
          b.classList.remove('active');
        }
      });
      fetchColdCalling();
    });
  }

  const ccSearch = document.getElementById('filter-cold-calling-search');
  if (ccSearch) {
    let ccDebounce = null;
    ccSearch.addEventListener('input', () => {
      clearTimeout(ccDebounce);
      ccDebounce = setTimeout(() => {
        State.coldCallingFilter.search = ccSearch.value.trim();
        fetchColdCalling();
      }, 250);
    });
  }

  const ccPotential = document.getElementById('filter-cold-calling-potential');
  if (ccPotential) {
    ccPotential.addEventListener('change', () => {
      State.coldCallingFilter.potential = ccPotential.value;
      fetchColdCalling();
    });
  }

  const ccCity = document.getElementById('filter-cold-calling-city');
  if (ccCity) {
    ccCity.addEventListener('change', () => {
      State.coldCallingFilter.city = ccCity.value;
      fetchColdCalling();
    });
  }

  const btnResetCC = document.getElementById('btn-reset-cold-calling-filters');
  if (btnResetCC) {
    btnResetCC.addEventListener('click', () => {
      State.coldCallingFilter = { tab: 'ALL', call_status: '', search: '', priority: '', potential: '', city: '' };
      document.querySelectorAll('#cold-calling-tabs-bar button[data-call-status]').forEach(b => {
        if (b.getAttribute('data-call-status') === 'ALL') b.classList.add('active');
        else b.classList.remove('active');
      });
      document.querySelectorAll('#cold-calling-tabs-bar button[data-tab]').forEach(b => {
        if (b.getAttribute('data-tab') === 'ALL') b.classList.add('active');
        else b.classList.remove('active');
      });
      if (ccStatusSelect) ccStatusSelect.value = '';
      if (ccSearch) ccSearch.value = '';
      if (ccPotential) ccPotential.value = '';
      if (ccCity) ccCity.value = '';
      fetchColdCalling();
    });
  }

  // Instagram filter listeners
  const igSearch = document.getElementById('filter-ig-search');
  if (igSearch) {
    let igDebounce = null;
    igSearch.addEventListener('input', () => {
      clearTimeout(igDebounce);
      igDebounce = setTimeout(() => {
        State.igFilter.search = igSearch.value.trim();
        fetchInstagram();
      }, 250);
    });
  }

  const igPotential = document.getElementById('filter-ig-potential');
  if (igPotential) {
    igPotential.addEventListener('change', () => {
      State.igFilter.potential = igPotential.value;
      fetchInstagram();
    });
  }

  const igCity = document.getElementById('filter-ig-city');
  if (igCity) {
    igCity.addEventListener('change', () => {
      State.igFilter.city = igCity.value;
      fetchInstagram();
    });
  }

  const btnResetIg = document.getElementById('btn-reset-ig-filters');
  if (btnResetIg) {
    btnResetIg.addEventListener('click', () => {
      State.igFilter = { search: '', potential: '', city: '' };
      if (igSearch) igSearch.value = '';
      if (igPotential) igPotential.value = '';
      if (igCity) igCity.value = '';
      fetchInstagram();
    });
  }

  // Pagination controls
  document.getElementById('btn-prev-page').addEventListener('click', () => {
    if (State.leadsPage > 1) {
      State.leadsPage--;
      fetchMasterLeads();
    }
  });

  document.getElementById('btn-next-page').addEventListener('click', () => {
    if (State.leadsPage < State.leadsTotalPages) {
      State.leadsPage++;
      fetchMasterLeads();
    }
  });

  // Export CSV
  document.getElementById('btn-export-csv').addEventListener('click', () => {
    exportCurrentLeadsCSV();
  });
}

function filterWhatsAppByCard(status) {
  State.waFilter.status = status;
  const sel = document.getElementById('filter-wa-status');
  if (sel) sel.value = status;
  fetchWhatsApp();
}

/* --------------------------------------------------------------------------
   API Fetchers & Renderers
   -------------------------------------------------------------------------- */

function buildQueryString(extraParams = {}) {
  const params = new URLSearchParams({
    date_filter: State.dateFilter,
    custom_start: State.customStart,
    custom_end: State.customEnd,
    search: State.searchQuery,
    ...extraParams,
  });
  return params.toString();
}

async function fetchOverview() {
  try {
    const res = await fetch(`/api/overview?${buildQueryString()}`);
    if (!res.ok) throw new Error('Failed to fetch overview data');
    const data = await res.json();
    renderOverview(data);
  } catch (err) {
    console.error('Overview error:', err);
  }
}

function renderOverview(data) {
  const kpis = data.kpis || {};
  const today = data.today || {};
  const wa = data.whatsapp_summary || {};
  const ch = data.channels || {};

  // Update Badges in Sidebar
  document.getElementById('badge-today-count').textContent = today.total_discovered_today || 0;
  document.getElementById('badge-total-leads').textContent = data.total_leads_all_time || 0;
  document.getElementById('badge-wa-sent').textContent = wa.SENT || 0;
  document.getElementById('badge-cold-calls').textContent = ch.COLD_CALLING || 0;
  document.getElementById('badge-ig-leads').textContent = ch.INSTAGRAM || 0;
  document.getElementById('badge-attention').textContent = (data.attention_items || []).length;
  document.getElementById('badge-sources-count').textContent = data.sources_discovered_count || 0;

  // Update KPI Cards
  document.getElementById('kpi-total-leads').textContent = (kpis.TOTAL_LEADS || 0).toLocaleString();
  const elActive = document.getElementById('kpi-active-leads');
  if (elActive) elActive.textContent = (kpis.ACTIVE_LEADS || 0).toLocaleString();
  const elArch = document.getElementById('kpi-archived-leads');
  if (elArch) elArch.textContent = (kpis.ARCHIVED_LEADS || 0).toLocaleString();
  const elSkip = document.getElementById('kpi-skipped-leads');
  if (elSkip) elSkip.textContent = (kpis.SKIPPED_LEADS || 0).toLocaleString();

  document.getElementById('kpi-today-leads').textContent = (kpis.TODAY_LEADS || 0).toLocaleString();
  document.getElementById('kpi-contact-first').textContent = (kpis.CONTACT_FIRST || 0).toLocaleString();
  document.getElementById('kpi-high-potential').textContent = (kpis.HIGH_POTENTIAL || 0).toLocaleString();
  document.getElementById('kpi-wa-sent').textContent = (kpis.WHATSAPP_SENT || 0).toLocaleString();
  document.getElementById('kpi-wa-failed').textContent = (kpis.WHATSAPP_FAILED || 0).toLocaleString();
  document.getElementById('kpi-wa-pending').textContent = (kpis.WHATSAPP_PENDING || 0).toLocaleString();
  document.getElementById('kpi-ig-leads').textContent = (kpis.INSTAGRAM_DM_LEADS || 0).toLocaleString();
  document.getElementById('kpi-cold-calls').textContent = (kpis.COLD_CALLS_PENDING || 0).toLocaleString();
  
  const rev = kpis.REVENUE_GENERATED || 0;
  document.getElementById('kpi-pipeline-value').textContent = `PKR ${rev.toLocaleString()}`;
  document.getElementById('kpi-won-count').textContent = `${kpis.WON_CLIENTS || 0} clients won`;

  // Render Milestone Funnel
  renderFunnel(data.milestones || {}, data.total_leads_all_time || 1);

  // Render Needs Attention Quick Feed
  renderQuickAttention(data.attention_items || []);

  // Render Recent Activity Quick Feed
  renderQuickActivity(data.recent_activity || []);

  // Render Top Cities
  renderTopCities(data.geography || {});

  // Render Top Channels
  renderTopChannels(data.channels || {});
}

function renderFunnel(milestones, total) {
  const container = document.getElementById('funnel-container');
  if (!container) return;

  const steps = [
    { label: 'M1 Ingestion & Discovery', count: milestones.M1_INGESTION || 0, color: 'var(--primary-blue)' },
    { label: 'M2 Digital Research Audited', count: milestones.M2_RESEARCH || 0, color: 'var(--accent-purple)' },
    { label: 'M3 AI Qualified Leads', count: milestones.M3_QUALIFICATION || 0, color: 'var(--accent-amber)' },
    { label: 'M4 Personalized Copy Generated', count: milestones.M4_OUTREACH_READY || 0, color: 'var(--primary-blue-hover)' },
    { label: 'M5 Master Contact Ready', count: milestones.M5_MASTER_READY || 0, color: 'var(--accent-insta)' },
    { label: 'M6 WhatsApp Ground-Truth Sent', count: milestones.M6_WHATSAPP_SENT || 0, color: 'var(--accent-green)' },
  ];

  const maxVal = Math.max(1, ...steps.map(s => s.count));

  container.innerHTML = steps.map(s => {
    const pct = Math.min(100, Math.round((s.count / maxVal) * 100));
    return `
      <div>
        <div style="display:flex; justify-content:space-between; font-size:11.5px; margin-bottom:3px;">
          <span style="color:var(--text-muted); font-weight:500;">${s.label}</span>
          <span style="font-weight:700; color:var(--text-main);">${s.count.toLocaleString()}</span>
        </div>
        <div style="background:var(--bg-input); height:6px; border-radius:3px; overflow:hidden;">
          <div style="background:${s.color}; width:${pct}%; height:100%; border-radius:3px; transition:width 0.4s ease;"></div>
        </div>
      </div>
    `;
  }).join('');
}

function renderQuickAttention(items) {
  const container = document.getElementById('dashboard-attention-list');
  if (!container) return;

  if (!items || items.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding:24px; color:var(--text-dim); font-size:12px;">✅ No urgent blockers right now. Pipeline is clean!</div>`;
    return;
  }

  container.innerHTML = items.slice(0, 5).map(item => `
    <div class="timeline-item" onclick="openLeadModal('${escapeJsString(item.lead_id)}')">
      <div class="timeline-icon" style="color:var(--accent-red);">🚨</div>
      <div class="timeline-content">
        <div class="timeline-title">${escapeHtml(item.business_name || item.lead_id)}</div>
        <div class="timeline-desc">${escapeHtml(item.reason)}</div>
      </div>
      <span class="badge badge-skip">${escapeHtml(item.type)}</span>
    </div>
  `).join('');
}

function renderQuickActivity(events) {
  const container = document.getElementById('dashboard-activity-list');
  if (!container) return;

  if (!events || events.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding:24px; color:var(--text-dim); font-size:12px;">No activity logged for this time window.</div>`;
    return;
  }

  container.innerHTML = events.slice(0, 5).map(ev => {
    const timeStr = formatTimestamp(ev.timestamp);
    const icon = getMilestoneIcon(ev.milestone);
    return `
      <div class="timeline-item" onclick="openLeadModal('${escapeJsString(ev.lead_id)}')">
        <div class="timeline-icon">${icon}</div>
        <div class="timeline-content">
          <div class="timeline-title">${escapeHtml(ev.business_name || ev.lead_id)}</div>
          <div class="timeline-desc">${escapeHtml(ev.details)}</div>
        </div>
        <div class="timeline-time">${timeStr}</div>
      </div>
    `;
  }).join('');
}

function renderTopCities(geo) {
  const container = document.getElementById('dashboard-city-list');
  if (!container) return;

  const entries = Object.entries(geo).sort((a, b) => b[1] - a[1]).slice(0, 5);
  if (entries.length === 0) {
    container.innerHTML = `<div style="color:var(--text-dim); font-size:11px;">No city data</div>`;
    return;
  }

  const max = Math.max(1, ...entries.map(e => e[1]));
  container.innerHTML = entries.map(([city, count]) => {
    const pct = Math.round((count / max) * 100);
    return `
      <div style="font-size:11.5px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
          <span style="color:var(--text-muted);">${escapeHtml(city)}</span>
          <span style="color:var(--text-main); font-weight:600;">${count}</span>
        </div>
        <div style="background:var(--bg-input); height:4px; border-radius:2px; overflow:hidden;">
          <div style="background:var(--primary-blue); width:${pct}%; height:100%;"></div>
        </div>
      </div>
    `;
  }).join('');
}

function renderTopChannels(channels) {
  const container = document.getElementById('dashboard-channel-list');
  if (!container) return;

  const list = [
    { name: 'WhatsApp', count: channels.WHATSAPP || 0, color: 'var(--accent-wa)' },
    { name: 'Instagram DM', count: channels.INSTAGRAM || 0, color: 'var(--accent-insta)' },
    { name: 'Cold Calling', count: channels.COLD_CALLING || 0, color: 'var(--primary-blue)' },
    { name: 'Email', count: channels.EMAIL || 0, color: 'var(--accent-amber)' },
  ];

  const max = Math.max(1, ...list.map(c => c.count));
  container.innerHTML = list.map(c => {
    const pct = Math.round((c.count / max) * 100);
    return `
      <div style="font-size:11.5px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
          <span style="color:var(--text-muted);">${c.name}</span>
          <span style="color:var(--text-main); font-weight:600;">${c.count}</span>
        </div>
        <div style="background:var(--bg-input); height:4px; border-radius:2px; overflow:hidden;">
          <div style="background:${c.color}; width:${pct}%; height:100%;"></div>
        </div>
      </div>
    `;
  }).join('');
}

/* --------------------------------------------------------------------------
   Today's Activity View
   -------------------------------------------------------------------------- */

async function fetchActivity() {
  try {
    const res = await fetch(`/api/activity/today`);
    if (!res.ok) throw new Error('Failed to fetch today activity');
    const data = await res.json();
    renderActivityView(data.events || []);
  } catch (err) {
    console.error('Activity error:', err);
  }
}

function renderActivityView(events) {
  const container = document.getElementById('full-activity-feed');
  if (!container) return;

  const sentCount = events.filter(e => e.milestone === 'M6_WHATSAPP' && e.status === 'SENT').length;
  const discCount = events.filter(e => e.milestone === 'M1_INPUT').length;

  document.getElementById('activity-sent-badge').textContent = `${sentCount} WhatsApp Sent`;
  document.getElementById('activity-discovered-badge').textContent = `${discCount} Leads Ingested`;
  document.getElementById('activity-date-display').textContent = new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric' });

  if (events.length === 0) {
    container.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-dim);">No activity records detected for today yet. Run a pipeline batch or ingest leads to see live events.</div>`;
    return;
  }

  container.innerHTML = events.map(ev => {
    const icon = getMilestoneIcon(ev.milestone);
    const timeStr = formatTimestamp(ev.timestamp);
    return `
      <div class="timeline-item" onclick="openLeadModal('${escapeJsString(ev.lead_id)}')">
        <div class="timeline-icon">${icon}</div>
        <div class="timeline-content">
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="timeline-title">${escapeHtml(ev.business_name || ev.lead_id)}</span>
            <span class="badge ${getMilestoneBadgeClass(ev.milestone)}">${escapeHtml(ev.milestone)}</span>
            ${ev.status ? `<span class="badge ${getStatusBadgeClass(ev.status)}">${escapeHtml(ev.status)}</span>` : ''}
          </div>
          <div class="timeline-desc">${escapeHtml(ev.details)}</div>
        </div>
        <div class="timeline-time">${timeStr}</div>
      </div>
    `;
  }).join('');
}

/* --------------------------------------------------------------------------
   Visual Sales Pipeline (Kanban)
   -------------------------------------------------------------------------- */

async function fetchPipeline() {
  try {
    const res = await fetch(`/api/pipeline?${buildQueryString()}`);
    if (!res.ok) throw new Error('Failed to fetch pipeline');
    const data = await res.json();
    renderPipeline(data.stages || {});
  } catch (err) {
    console.error('Pipeline error:', err);
  }
}

function renderPipeline(stages) {
  const container = document.getElementById('kanban-board-container');
  if (!container) return;

  const colDefinitions = [
    { key: 'NEW', title: '📥 Ingested (M1)', color: 'var(--primary-blue)' },
    { key: 'RESEARCHED', title: '🔬 Researched (M2)', color: 'var(--accent-purple)' },
    { key: 'QUALIFIED', title: '⚖️ Qualified (M3)', color: 'var(--accent-amber)' },
    { key: 'READY_TO_CONTACT', title: '✉️ Ready to Contact (M4/M5)', color: 'var(--primary-blue-hover)' },
    { key: 'CONTACTED', title: '💬 Contacted / Sent (M6)', color: 'var(--accent-wa)' },
    { key: 'REPLIED', title: '🔄 Replied / Engaged', color: 'var(--accent-insta)' },
    { key: 'INTERESTED', title: '🔥 High Interest / Meeting', color: 'var(--accent-green)' },
    { key: 'WON', title: '🏆 Closed Won ($)', color: 'var(--accent-green)' },
    { key: 'LOST', title: '❌ Lost / Closed', color: 'var(--text-dim)' },
  ];

  const searchFilter = (document.getElementById('kanban-search')?.value || '').toLowerCase();

  container.innerHTML = colDefinitions.map(col => {
    let list = stages[col.key] || [];
    if (searchFilter) {
      list = list.filter(l => (l.business_name || '').toLowerCase().includes(searchFilter) || (l.phone || '').includes(searchFilter));
    }

    const cardsHtml = list.map(item => `
      <div class="kanban-card" onclick="openLeadModal('${escapeJsString(item.lead_id)}')">
        <div class="kanban-card-title">${escapeHtml(item.business_name || item.lead_id)}</div>
        <div style="font-size:11px; color:var(--text-muted); display:flex; justify-content:space-between;">
          <span>${escapeHtml(item.city || 'Pakistan')}</span>
          <span style="color:var(--text-main); font-family:var(--font-mono);">${escapeHtml(item.phone || 'No Phone')}</span>
        </div>
        <div class="kanban-card-meta">
          <span style="font-family:var(--font-mono); font-size:10px; font-weight:700; color:var(--text-main); background:var(--bg-input); padding:1px 5px; border-radius:3px; border:1px solid var(--border-color);">${item.qualification_score !== undefined && item.qualification_score !== null ? item.qualification_score : '—'}</span>
          <span class="badge ${getPotentialBadgeClass(item.potential)}">${escapeHtml(item.potential || 'MOD')}</span>
          <span class="badge ${getStatusBadgeClass(item.m6_status)}">${escapeHtml(item.m6_status || 'PENDING')}</span>
        </div>
      </div>
    `).join('');

    return `
      <div class="kanban-col">
        <div class="kanban-col-header" style="border-top: 3px solid ${col.color};">
          <span>${col.title}</span>
          <span class="badge badge-low">${list.length}</span>
        </div>
        <div class="kanban-cards">
          ${cardsHtml || `<div style="text-align:center; padding:20px; color:var(--text-dim); font-size:11px;">No leads</div>`}
        </div>
      </div>
    `;
  }).join('');

  // Kanban search live filter
  const kanbanInput = document.getElementById('kanban-search');
  if (kanbanInput && !kanbanInput.dataset.bound) {
    kanbanInput.dataset.bound = 'true';
    kanbanInput.addEventListener('input', () => {
      renderPipeline(stages);
    });
  }
}

/* --------------------------------------------------------------------------
   Master Leads Table View
   -------------------------------------------------------------------------- */

async function fetchMasterLeads() {
  try {
    const extraParams = {
      page: State.leadsPage,
      limit: State.leadsLimit,
      tab: State.leadsTab,
      niche: State.leadsFilter.niche,
      country: State.leadsFilter.country,
      city: State.leadsFilter.city,
      priority: State.leadsFilter.priority,
      potential: State.leadsFilter.potential,
      channel: State.leadsFilter.channel,
      status: State.leadsFilter.status,
      milestone: State.leadsFilter.milestone,
      city: State.leadsFilter.city,
      call_status: State.leadsFilter.call_status,
      category: State.leadsFilter.category,
      activity: State.leadsFilter.activity,
      sort_by: State.leadsFilter.sort_by,
    };

    const res = await fetch(`/api/leads?${buildQueryString(extraParams)}`);
    if (!res.ok) throw new Error('Failed to fetch leads');
    const data = await res.json();
    renderMasterLeads(data);
  } catch (err) {
    console.error('Leads error:', err);
  }
}

function renderMasterLeads(data) {
  const tbody = document.getElementById('master-leads-tbody');
  if (!tbody) return;

  const leads = data.leads || [];
  const pag = data.pagination || { page: 1, total_pages: 1, total_matching: 0, limit: 50 };
  const tabCounts = data.tab_counts || {};

  State.leadsPage = pag.page;
  State.leadsTotalPages = pag.total_pages;
  State.currentLeads = leads;
  State.leadsMap = new Map();
  leads.forEach(l => State.leadsMap.set(l.lead_id, l));

  // Update tab counts
  if (tabCounts.ALL !== undefined) {
    const setTabCount = (id, count) => {
      const el = document.getElementById(id);
      if (el) el.textContent = (count || 0).toLocaleString();
    };
    setTabCount('tab-count-watches', tabCounts.WATCHES);
    setTabCount('tab-count-all', tabCounts.ALL);
    setTabCount('tab-count-new', tabCounts.NEW);
    setTabCount('tab-count-active', tabCounts.ACTIVE);
    setTabCount('tab-count-contact-first', tabCounts.CONTACT_FIRST);
    setTabCount('tab-count-contact-later', tabCounts.CONTACT_LATER);
    setTabCount('tab-count-high-potential', tabCounts.HIGH_POTENTIAL);
    setTabCount('tab-count-sent', tabCounts.SENT);
    setTabCount('tab-count-failed', tabCounts.FAILED);
    setTabCount('tab-count-not-ready', tabCounts.NOT_READY);
    setTabCount('tab-count-archive', tabCounts.ARCHIVE);
    setTabCount('tab-count-skip', tabCounts.SKIP);
  }

  document.getElementById('leads-count-tag').textContent = `${pag.total_matching.toLocaleString()} Leads`;
  
  const startIdx = pag.total_matching === 0 ? 0 : (pag.page - 1) * pag.limit + 1;
  const endIdx = Math.min(pag.total_matching, pag.page * pag.limit);
  document.getElementById('leads-page-info').textContent = `Showing ${startIdx}-${endIdx} of ${pag.total_matching.toLocaleString()}`;

  document.getElementById('btn-prev-page').disabled = (State.leadsPage <= 1);
  document.getElementById('btn-next-page').disabled = (State.leadsPage >= State.leadsTotalPages);

  if (leads.length === 0) {
    const allCountStr = (tabCounts.ALL || 0).toLocaleString();
    let dateLabel = 'selected date filter';
    if (State.dateFilter === 'TODAY') dateLabel = 'Today (Aaj)';
    else if (State.dateFilter === 'YESTERDAY') dateLabel = 'Yesterday (Kal)';
    else if (State.dateFilter === 'PARSO') dateLabel = 'Day Before Yesterday (Parso)';
    else if (State.dateFilter === 'SPECIFIC_DATE') dateLabel = `Date: ${State.customStart || 'Selected Date'}`;
    else if (State.dateFilter === 'CUSTOM') dateLabel = `Range: ${State.customStart} to ${State.customEnd}`;

    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align:center; padding:36px 20px;">
          <div style="font-size:28px; margin-bottom:8px;">📅</div>
          <div style="font-size:15px; font-weight:700; color:var(--text-main); margin-bottom:6px;">No Leads Found for "${dateLabel}"</div>
          <div style="font-size:12px; color:var(--text-muted); max-width:520px; margin:0 auto 16px auto; line-height:1.6;">
            Pipeline mein leads previous dates par ingest aur verify hui hain. Aap foran niche diye gaye buttons se Kal ya Parso ki leads dekh sakhte hain:
          </div>
          <div style="display:flex; justify-content:center; gap:8px; flex-wrap:wrap;">
            <button class="btn btn-sm" onclick="setGlobalDateFilter('YESTERDAY')" style="background:rgba(56,189,248,0.15); border-color:#38bdf8; color:#38bdf8; font-weight:700; padding:6px 14px; cursor:pointer;">
              ⏮️ Kal / Yesterday (78 Leads)
            </button>
            <button class="btn btn-sm" onclick="setGlobalDateFilter('PARSO')" style="background:rgba(168,85,247,0.15); border-color:#c084fc; color:#c084fc; font-weight:700; padding:6px 14px; cursor:pointer;">
              ⏳ Parso (23 Leads)
            </button>
            <button class="btn btn-sm btn-primary" onclick="resetDateFilterToAllTime()" style="background:#2563eb; border-color:#2563eb; font-weight:700; padding:6px 14px; cursor:pointer;">
              📅 Show All Time (${allCountStr} Leads)
            </button>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = leads.map(l => {
    const isArch = Boolean(l.is_archived || l.sales_stage === 'ARCHIVED');
    const isSkip = Boolean(l.is_skipped || l.sales_stage === 'SKIPPED');
    const waLink = (!isArch && !isSkip && (l.m6_recipient || l.phone)) ? `https://wa.me/${(l.m6_recipient || l.phone).replace(/[^0-9]/g, '')}` : '';
    const m6DisplayStatus = isArch ? 'ARCHIVE' : (isSkip ? 'SKIP' : (l.m6_status || 'PENDING'));
    const callStatus = l.call_status || 'PENDING';
    const crmCategory = l.category || '';
    const lastCalled = l.last_called_at ? formatRelativeTime(l.last_called_at) : '';
    const notePreview = l.latest_note || '';
    const leadDate = l.discovered_at ? l.discovered_at.slice(0, 10) : (l.researched_at ? l.researched_at.slice(0, 10) : '');

    // Safely encode lead data for inline button handler
    const leadJson = escapeAttr(JSON.stringify({
      lead_id: l.lead_id,
      business_name: l.business_name || l.lead_id,
      phone: l.phone || '',
      call_status: callStatus,
      category: crmCategory,
      latest_note: notePreview,
      last_called_at: l.last_called_at || '',
    }));

    return `
      <tr onclick="openLeadModal('${escapeJsString(l.lead_id)}')" style="cursor:pointer;" title="Click any row to open complete M1-M5 lead details">
        <td>
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:6px;">
            <div>
              <div style="font-weight:600; color:var(--text-main); cursor:pointer;" onclick="openLeadModal('${escapeJsString(l.lead_id)}')" title="Click to view M1-M5 Pipeline Details">
                ${escapeHtml(l.business_name || l.lead_id)}
              </div>
              <div style="font-size:11px; color:var(--text-muted); margin-top:2px; display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                <span>${escapeHtml(l.city || l.location || '—')}</span>
                <span>•</span>
                <span style="font-family:var(--font-mono);">${escapeHtml(l.lead_id)}</span>
                ${leadDate ? `<span class="badge" style="background:rgba(56,189,248,0.1); color:#38bdf8; font-size:10px; padding:1px 5px;" title="Date Lead Added">📅 ${escapeHtml(leadDate)}</span>` : ''}
              </div>
            </div>
            <button class="btn btn-sm" onclick="event.stopPropagation(); openLeadModal('${escapeJsString(l.lead_id)}')" style="font-size:10px; padding:2px 7px; background:rgba(56,189,248,0.12); color:#38bdf8; border:1px solid rgba(56,189,248,0.35); font-weight:700; border-radius:4px; white-space:nowrap; cursor:pointer;" title="Inspect what happened in M1 to M5">🔍 M1-M5</button>
          </div>
        </td>
        <td>
          <div>
            ${l.phone ? `<a href="tel:${escapeAttr(l.phone)}" onclick="event.stopPropagation();" style="font-family:var(--font-mono); font-size:11.5px; color:#38bdf8; text-decoration:none;">📞 ${escapeHtml(l.phone)}</a>` : '<span style="color:var(--text-dim); font-size:11px;">No Phone</span>'}
            ${waLink ? `<a href="${waLink}" target="_blank" onclick="event.stopPropagation();" style="margin-left:4px; font-size:11px; color:var(--accent-wa); text-decoration:none;" title="Open WhatsApp">💬</a>` : ''}
          </div>
          ${l.instagram ? `<div style="font-size:10.5px; color:var(--accent-insta);">📸 @${escapeHtml(l.instagram)}</div>` : ''}
        </td>
        <td onclick="event.stopPropagation();">
          <select class="badge-select ${getStatusBadgeClass(m6DisplayStatus)}" 
                  title="Click to manually edit M6 status"
                  onchange="quickChangeM6Status('${escapeJsString(l.lead_id)}', this.value)" 
                  onclick="event.stopPropagation();">
            <option value="SENT" ${m6DisplayStatus === 'SENT' ? 'selected' : ''}>✅ SENT</option>
            <option value="PENDING" ${m6DisplayStatus === 'PENDING' ? 'selected' : ''}>⏳ PENDING</option>
            <option value="AWAITING_MANUAL_SEND" ${m6DisplayStatus === 'AWAITING_MANUAL_SEND' ? 'selected' : ''}>✋ MANUAL</option>
            <option value="FAILED" ${m6DisplayStatus === 'FAILED' ? 'selected' : ''}>❌ FAILED</option>
            <option value="NOT_READY" ${m6DisplayStatus === 'NOT_READY' ? 'selected' : ''}>⚠️ NOT READY</option>
            <option value="NO_WHATSAPP_NUMBER" ${m6DisplayStatus === 'NO_WHATSAPP_NUMBER' ? 'selected' : ''}>🚫 NO WA</option>
            <option value="ARCHIVE" ${m6DisplayStatus === 'ARCHIVE' ? 'selected' : ''}>📁 ARCHIVE</option>
            <option value="SKIP" ${m6DisplayStatus === 'SKIP' ? 'selected' : ''}>⏭️ SKIP</option>
          </select>
        </td>
        <td>
          <span class="badge ${getCrmCallBadgeClass(callStatus)}">${escapeHtml(callStatus)}</span>
        </td>
        <td>
          <span class="badge ${getCrmCategoryBadgeClass(crmCategory)}">${escapeHtml(crmCategory ? getCategoryDisplay(crmCategory) : '—')}</span>
        </td>
        <td style="max-width:200px;">
          <div>${lastCalled ? `<span style="font-size:11px; color:var(--text-main); font-weight:600;">🕒 ${lastCalled}</span>` : '<span style="color:var(--text-dim); font-size:11px;">Never Called</span>'}</div>
          ${notePreview ? `<div style="font-size:11px; color:var(--text-muted); font-style:italic; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeAttr(notePreview)}">"${escapeHtml(notePreview)}"</div>` : ''}
        </td>
        <td>
          <div style="display:flex; align-items:center; gap:4px; flex-wrap:wrap;">
            <span class="badge ${getPotentialBadgeClass(l.sales_potential)}" style="font-size:10px;">${escapeHtml(l.sales_potential || 'MOD')}</span>
            <span class="badge ${getChannelBadgeClass(l.outreach_channel)}" style="font-size:10px;">${escapeHtml(l.outreach_channel || 'WA')}</span>
          </div>
        </td>
        <td onclick="event.stopPropagation();" style="white-space:nowrap;">
          <div style="display:flex; gap:4px; align-items:center;">
            <button class="btn btn-sm" title="View Complete M1-M5 Pipeline Details" onclick="event.stopPropagation(); openLeadModal('${escapeJsString(l.lead_id)}')" style="background:rgba(56,189,248,0.15); border:1px solid #38bdf8; color:#38bdf8; font-weight:700; padding:2px 8px; cursor:pointer;">👁 Details</button>
            <button class="btn btn-sm btn-primary" title="Quick Call Workflow" onclick="event.stopPropagation(); openQuickCallModal('${escapeJsString(l.lead_id)}')" style="background:#2563eb; border-color:#2563eb; font-weight:600; padding:2px 7px;">📞 Call Done</button>
            <button class="btn btn-sm" title="Mark Connected" onclick="event.stopPropagation(); quickRowCallStatus('${escapeJsString(l.lead_id)}', 'CONNECTED')" style="border-color:#34d399; color:#34d399; padding:2px 6px;">🟢</button>
            <button class="btn btn-sm" title="Mark Not Connected" onclick="event.stopPropagation(); quickRowCallStatus('${escapeJsString(l.lead_id)}', 'NOT_CONNECTED')" style="border-color:#f87171; color:#f87171; padding:2px 6px;">🔴</button>
            <button class="btn btn-sm" title="Mark Interested" onclick="event.stopPropagation(); quickRowCategory('${escapeJsString(l.lead_id)}', 'INTERESTED')" style="border-color:#38bdf8; color:#38bdf8; font-weight:700; padding:2px 6px;">💎 A</button>
            <button class="btn btn-sm" title="Mark Send" onclick="event.stopPropagation(); quickRowCategory('${escapeJsString(l.lead_id)}', 'SEND')" style="border-color:#c084fc; color:#c084fc; font-weight:700; padding:2px 6px;">🚀 B</button>
            <button class="btn btn-sm" title="Mark No Answer" onclick="event.stopPropagation(); quickRowCategory('${escapeJsString(l.lead_id)}', 'NO_ANSWER')" style="border-color:#fb923c; color:#fb923c; font-weight:700; padding:2px 6px;">📵 C</button>
            <button class="btn btn-sm" title="Add Note" onclick="event.stopPropagation(); openQuickCallModal('${escapeJsString(l.lead_id)}')" style="padding:2px 6px;">📝</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

/* --------------------------------------------------------------------------
   WhatsApp Center View
   -------------------------------------------------------------------------- */

async function fetchWhatsApp() {
  try {
    const res = await fetch(`/api/whatsapp?${buildQueryString({
      status: State.waFilter.status,
      search: State.waFilter.search,
      city: State.waFilter.city,
    })}`);
    if (!res.ok) throw new Error('Failed to fetch WhatsApp page');
    const data = await res.json();
    renderWhatsApp(data);
  } catch (err) {
    console.error('WhatsApp error:', err);
  }
}

function renderWhatsApp(data) {
  const counts = data.counts || {};
  document.getElementById('wa-card-total').textContent = (counts.TOTAL_WHATSAPP_ELIGIBLE || 0).toLocaleString();
  document.getElementById('wa-card-sent').textContent = (counts.SENT || 0).toLocaleString();
  document.getElementById('wa-card-failed').textContent = (counts.FAILED || 0).toLocaleString();
  document.getElementById('wa-card-pending').textContent = (counts.PENDING || 0).toLocaleString();
  document.getElementById('wa-card-no-wa').textContent = (counts.NO_WHATSAPP_NUMBER || 0).toLocaleString();

  const tbody = document.getElementById('wa-leads-tbody');
  if (!tbody) return;

  const leads = data.leads || [];
  if (leads.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-dim);">No WhatsApp records matching this filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = leads.map(l => {
    const phoneNum = l.m6_recipient || l.phone || '';
    const cleanNum = phoneNum.replace(/[^0-9]/g, '');
    const waLink = cleanNum ? `https://wa.me/${cleanNum}` : '';

    return `
      <tr onclick="openLeadModal('${escapeJsString(l.lead_id)}')">
        <td>
          <div style="font-weight:600; color:var(--text-main);">${escapeHtml(l.business_name || l.lead_id)}</div>
          <div style="font-size:11px; color:var(--text-dim);">${escapeHtml(l.city || 'Islamabad/Rwp')}</div>
        </td>
        <td style="font-family:var(--font-mono); color:var(--text-main);">${phoneNum ? escapeHtml(phoneNum) : '<span style="color:var(--text-dim);">No Number</span>'}</td>
        <td onclick="event.stopPropagation();">
          <select class="badge-select ${getStatusBadgeClass(l.m6_status || 'PENDING')}" 
                  title="Click to manually edit WhatsApp status"
                  onchange="quickChangeM6Status('${escapeJsString(l.lead_id)}', this.value)" 
                  onclick="event.stopPropagation();">
            <option value="SENT" ${(l.m6_status === 'SENT') ? 'selected' : ''}>✅ SENT</option>
            <option value="PENDING" ${(l.m6_status === 'PENDING' || !l.m6_status) ? 'selected' : ''}>⏳ PENDING</option>
            <option value="SKIPPED_LIMIT" ${(l.m6_status === 'SKIPPED_LIMIT') ? 'selected' : ''}>⏱️ LIMIT REACHED</option>
            <option value="AWAITING_MANUAL_SEND" ${(l.m6_status === 'AWAITING_MANUAL_SEND') ? 'selected' : ''}>✋ MANUAL</option>
            <option value="FAILED" ${(l.m6_status === 'FAILED') ? 'selected' : ''}>❌ FAILED</option>
            <option value="NOT_READY" ${(l.m6_status === 'NOT_READY') ? 'selected' : ''}>⚠️ NOT READY</option>
            <option value="NO_WHATSAPP_NUMBER" ${(l.m6_status === 'NO_WHATSAPP_NUMBER') ? 'selected' : ''}>🚫 NO WA</option>
            <option value="ARCHIVE" ${(l.m6_status === 'ARCHIVE') ? 'selected' : ''}>📁 ARCHIVE</option>
            <option value="SKIP" ${(l.m6_status === 'SKIP') ? 'selected' : ''}>⏭️ SKIP</option>
          </select>
        </td>
        <td style="font-family:var(--font-mono);">${l.m6_send_attempts || 0}</td>
        <td style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${formatTimestamp(l.m6_sent_at || l.m6_last_attempt_at)}</td>
        <td style="font-size:11.5px; color:var(--accent-amber); max-width:200px; word-break:break-word;">${escapeHtml(l.m6_error || '—')}</td>
        <td onclick="event.stopPropagation();">
          <div style="display:flex; gap:6px;">
            ${waLink ? `<a href="${waLink}" target="_blank" class="btn btn-sm" style="color:var(--accent-wa); background:var(--accent-wa-dim);">💬 Open WA</a>` : ''}
            ${l.outreach_message ? `<button class="btn btn-sm" onclick="copyPitchText('${escapeAttr(l.outreach_message)}')">📋 Pitch</button>` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

/* --------------------------------------------------------------------------
   Cold Calling View
   -------------------------------------------------------------------------- */

async function fetchColdCalling() {
  try {
    const res = await fetch(`/api/cold-calling?${buildQueryString({
      tab: State.coldCallingFilter.tab,
      call_status: State.coldCallingFilter.call_status,
      search: State.coldCallingFilter.search,
      potential: State.coldCallingFilter.potential,
      city: State.coldCallingFilter.city,
    })}`);
    if (!res.ok) throw new Error('Failed to fetch cold calling');
    const data = await res.json();
    renderColdCalling(data);
  } catch (err) {
    console.error('Cold calling error:', err);
  }
}

function renderColdCalling(data) {
  const counts = data.counts || {};
  const leads = data.leads || [];

  // Call Status counts
  const countCallAll = document.getElementById('cc-call-count-all');
  if (countCallAll) countCallAll.textContent = (counts.CALL_ALL || counts.ALL || 0).toLocaleString();

  const countCallPending = document.getElementById('cc-call-count-pending');
  if (countCallPending) countCallPending.textContent = (counts.CALL_PENDING || 0).toLocaleString();

  const countCallConnected = document.getElementById('cc-call-count-connected');
  if (countCallConnected) countCallConnected.textContent = (counts.CALL_CONNECTED || 0).toLocaleString();

  const countCallNotConnected = document.getElementById('cc-call-count-not-connected');
  if (countCallNotConnected) countCallNotConnected.textContent = (counts.CALL_NOT_CONNECTED || 0).toLocaleString();

  // Priority counts
  const countAll = document.getElementById('cc-tab-count-all');
  if (countAll) countAll.textContent = (counts.ALL || 0).toLocaleString();

  const countFirst = document.getElementById('cc-tab-count-first');
  if (countFirst) countFirst.textContent = (counts.CONTACT_FIRST || 0).toLocaleString();

  const countLater = document.getElementById('cc-tab-count-later');
  if (countLater) countLater.textContent = (counts.CONTACT_LATER || 0).toLocaleString();

  const headerCount = document.getElementById('cold-calling-count');
  if (headerCount) {
    const statusLabel = State.coldCallingFilter.call_status ? ` • ${State.coldCallingFilter.call_status.replace('_', ' ')}` : '';
    headerCount.textContent = `${leads.length} Callable Leads${statusLabel}`;
  }

  const tbody = document.getElementById('cold-calling-tbody');
  if (!tbody) return;

  if (leads.length === 0) {
    tbody.innerHTML = `<tr><td colspan="13" style="text-align:center; padding:32px; color:var(--text-dim);">No cold calling leads found matching this filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = leads.map(l => {
    const cleanNum = (l.whatsapp || l.phone || '').replace(/[^0-9]/g, '');
    const waLink = cleanNum ? `https://wa.me/${cleanNum}` : '';
    const srcName = l.source_file ? l.source_file.split('/').pop() : '—';
    const dateStr = formatDate(l.discovered_at || l.qualified_at);
    const callStatus = l.call_status || 'PENDING';
    const callDateStr = l.last_called_at ? formatTimestamp(l.last_called_at) : '';
    const isConn = callStatus === 'CONNECTED';
    const isNotConn = callStatus === 'NOT_CONNECTED';
    const statusBadgeClass = isConn ? 'badge-connected' : (isNotConn ? 'badge-not-connected' : 'badge-call-pending');
    const statusText = isConn ? '🟢 CONNECTED' : (isNotConn ? '🔴 NOT CONNECTED' : '⏳ PENDING');

    return `
      <tr onclick="openLeadModal('${escapeJsString(l.lead_id)}')">
        <td>
          <span style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted);">${escapeHtml(l.lead_id)}</span>
        </td>
        <td>
          <div style="font-weight:600; color:var(--text-main);">${escapeHtml(l.business_name || l.lead_id)}</div>
        </td>
        <td><span style="color:var(--text-muted); font-size:11.5px;">${escapeHtml(l.city || l.location || '—')}</span></td>
        <td>
          ${l.phone ? `<a href="tel:${escapeAttr(l.phone)}" onclick="event.stopPropagation();" style="font-family:var(--font-mono); font-weight:600; color:var(--primary-blue); font-size:11.5px; text-decoration:none;">📞 ${escapeHtml(l.phone)}</a>` : '<span style="color:var(--text-dim); font-size:11px;">—</span>'}
        </td>
        <td>
          <div style="display:inline-flex; flex-direction:column; gap:2px;">
            <span class="badge ${statusBadgeClass}" style="font-size:10px; font-weight:700; padding:2px 7px;">${statusText}</span>
            ${callDateStr ? `<span style="font-size:9.5px; color:var(--text-dim); font-family:var(--font-mono); margin-top:1px;">${callDateStr}</span>` : ''}
          </div>
        </td>
        <td>
          ${waLink ? `<a href="${waLink}" target="_blank" onclick="event.stopPropagation();" class="badge badge-sent" style="text-decoration:none; font-size:10px;">💬 Chat</a>` : '<span style="color:var(--text-dim); font-size:11px;">—</span>'}
        </td>
        <td>
          <span class="badge ${getPriorityBadgeClass(l.outreach_priority)}">${escapeHtml(l.outreach_priority || 'CONTACT FIRST')}</span>
        </td>
        <td>
          <div style="display:flex; align-items:center; gap:4px;">
            <span style="font-family:var(--font-mono); font-weight:700; color:var(--text-main); font-size:11.5px;">${l.qualification_score !== null && l.qualification_score !== undefined ? l.qualification_score : '—'}</span>
            <span class="badge ${getPotentialBadgeClass(l.sales_potential)}" style="font-size:9.5px; padding:1px 5px;">${escapeHtml(l.sales_potential || 'MOD')}</span>
          </div>
        </td>
        <td style="max-width:220px;">
          <div style="font-size:11.5px; color:var(--text-muted); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;" title="${escapeAttr(l.opportunity || l.why_this_lead || '')}">
            ${escapeHtml(l.opportunity || l.why_this_lead || '—')}
          </div>
        </td>
        <td style="max-width:240px;">
          <div style="font-size:11.5px; color:var(--accent-amber); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;" title="${escapeAttr(l.pitch_hook || l.outreach_message || '')}">
            ${escapeHtml(l.pitch_hook || l.outreach_message || '—')}
          </div>
        </td>
        <td>
          <span style="font-size:10.5px; color:var(--text-dim); font-family:var(--font-mono);">${escapeHtml(srcName)}</span>
        </td>
        <td>
          <span style="font-size:11px; color:var(--text-dim); font-family:var(--font-mono);">${dateStr}</span>
        </td>
        <td onclick="event.stopPropagation();" style="white-space:nowrap;">
          <div style="display:flex; gap:6px;">
            ${l.phone ? `<a href="tel:${escapeAttr(l.phone)}" class="btn btn-sm btn-primary" title="Call Now">📞 Call</a>` : ''}
            <button class="btn btn-sm btn-primary" title="Quick Call Workflow" onclick="event.stopPropagation(); openQuickCallModal('${escapeJsString(l.lead_id)}')" style="background:#2563eb; border-color:#2563eb; font-weight:600; padding:2px 7px;">📞 Call Done</button>
            <button class="btn btn-sm" title="Generate Personalized Boutique Demo" onclick="openLeadModal('${escapeJsString(l.lead_id)}', 'tab-demo')" style="color:#D4AF37; border-color:rgba(212,175,55,0.4); background:rgba(212,175,55,0.08); font-weight:600;">🚀 Demo</button>
            <button class="btn btn-sm" onclick="openLeadModal('${escapeJsString(l.lead_id)}')">Angle</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

/* --------------------------------------------------------------------------
   Instagram DMs View
   -------------------------------------------------------------------------- */

async function fetchInstagram() {
  try {
    const res = await fetch(`/api/instagram?${buildQueryString({
      search: State.igFilter.search,
      potential: State.igFilter.potential,
      city: State.igFilter.city,
    })}`);
    if (!res.ok) throw new Error('Failed to fetch Instagram page');
    const data = await res.json();
    renderInstagram(data.leads || []);
  } catch (err) {
    console.error('Instagram error:', err);
  }
}

function renderInstagram(leads) {
  const tbody = document.getElementById('ig-leads-tbody');
  if (!tbody) return;

  document.getElementById('ig-queue-count').textContent = `${leads.length} Actionable Leads`;

  if (leads.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:32px; color:var(--text-dim);">No Instagram queue leads found in manual_instagram_leads.csv.</td></tr>`;
    return;
  }

  tbody.innerHTML = leads.map(l => {
    const handle = (l.instagram || '').replace(/^@/, '');
    const igUrl = handle ? `https://instagram.com/${handle}` : '';
    const pitch = l.outreach_message || 'Assalam o Alaikum! I came across your boutique on Instagram...';

    return `
      <tr onclick="openLeadModal('${escapeJsString(l.lead_id)}')">
        <td>
          <div style="font-weight:600; color:var(--text-main);">${escapeHtml(l.business_name || l.lead_id)}</div>
          <span class="badge badge-insta" style="margin-top:3px;">No Direct Phone</span>
        </td>
        <td>
          ${handle ? `<a href="${igUrl}" target="_blank" onclick="event.stopPropagation();" style="color:var(--accent-insta); font-weight:600;">@${escapeHtml(handle)} ↗</a>` : '—'}
        </td>
        <td>${escapeHtml(l.city || '—')}</td>
        <td style="font-size:11.5px; color:var(--accent-amber);">${escapeHtml(l.gaps || 'Manual DM ordering bottleneck')}</td>
        <td style="max-width:320px;">
          <div style="font-size:11.5px; color:var(--text-muted); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">${escapeHtml(pitch)}</div>
        </td>
        <td onclick="event.stopPropagation();">
          <div style="display:flex; gap:6px;">
            ${handle ? `<a href="${igUrl}" target="_blank" class="btn btn-sm" style="color:var(--accent-insta); background:var(--accent-insta-dim);">📸 Open IG</a>` : ''}
            <button class="btn btn-sm btn-primary" onclick="copyPitchText('${escapeAttr(pitch)}')">📋 Copy DM Pitch</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

/* --------------------------------------------------------------------------
   Milestones M2, M3, M4, M5 Views
   -------------------------------------------------------------------------- */

async function fetchMilestoneM2() {
  const tbody = document.getElementById('m2-tbody');
  if (!tbody) return;

  const res = await fetch(`/api/leads?${buildQueryString({ limit: 100 })}`);
  const data = await res.json();
  const leads = data.leads || [];

  tbody.innerHTML = leads.map(l => `
    <tr onclick="openLeadModal('${escapeJsString(l.lead_id)}')">
      <td style="font-weight:600; color:var(--text-main);">${escapeHtml(l.business_name || l.lead_id)}</td>
      <td>${l.website ? `<a href="${escapeAttr(l.website)}" target="_blank" onclick="event.stopPropagation();" style="color:var(--primary-blue);">🌐 ${escapeHtml(l.website)}</a>` : '<span style="color:var(--text-dim);">None</span>'}</td>
      <td>${l.instagram ? `<span style="color:var(--accent-insta);">@${escapeHtml(l.instagram)}</span>` : '<span style="color:var(--text-dim);">None</span>'}</td>
      <td>${l.facebook ? `<span style="color:var(--primary-blue);">FB Profile</span>` : '<span style="color:var(--text-dim);">None</span>'}</td>
      <td>${l.tiktok ? `<span style="color:var(--accent-purple);">TikTok</span>` : '<span style="color:var(--text-dim);">None</span>'}</td>
      <td style="font-size:11.5px; color:var(--accent-amber);">${escapeHtml(l.gaps || '—')}</td>
      <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-dim);">${formatDate(l.researched_at || l.discovered_at)}</td>
    </tr>
  `).join('');
}

async function fetchMilestoneM3() {
  const tbody = document.getElementById('m3-tbody');
  if (!tbody) return;

  const res = await fetch(`/api/leads?${buildQueryString({ limit: 100 })}`);
  const data = await res.json();
  const leads = data.leads || [];

  tbody.innerHTML = leads.map(l => `
    <tr onclick="openLeadModal('${escapeJsString(l.lead_id)}')">
      <td style="font-weight:600; color:var(--text-main);">${escapeHtml(l.business_name || l.lead_id)}</td>
      <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-main);">${l.qualification_score !== null ? l.qualification_score : '—'}</td>
      <td><span class="badge ${getPotentialBadgeClass(l.sales_potential)}">${escapeHtml(l.sales_potential || 'MOD')}</span></td>
      <td><span class="badge ${getPriorityBadgeClass(l.outreach_priority)}">${escapeHtml(l.outreach_priority || 'CONTACT')}</span></td>
      <td style="color:var(--primary-blue);">${escapeHtml(l.primary_service || 'E-Commerce / Ads')}</td>
      <td style="font-size:11.5px; color:var(--text-muted); max-width:260px;">${escapeHtml(l.qualification_reasons || l.opportunity || '—')}</td>
    </tr>
  `).join('');
}

async function fetchMilestoneM4() {
  const tbody = document.getElementById('m4-tbody');
  if (!tbody) return;

  const res = await fetch(`/api/leads?${buildQueryString({ limit: 100 })}`);
  const data = await res.json();
  const leads = data.leads || [];

  tbody.innerHTML = leads.map(l => `
    <tr onclick="openLeadModal('${escapeJsString(l.lead_id)}')">
      <td style="font-weight:600; color:var(--text-main);">${escapeHtml(l.business_name || l.lead_id)}</td>
      <td><span class="badge ${getChannelBadgeClass(l.outreach_channel)}">${escapeHtml(l.outreach_channel || 'WhatsApp')}</span></td>
      <td style="color:var(--primary-blue); font-size:11.5px;">${escapeHtml(l.primary_service || 'Automation')}</td>
      <td style="font-family:var(--font-mono); font-size:11.5px;">${l.pitch_word_count || (l.outreach_message ? l.outreach_message.split(/\s+/).length : 0)}w</td>
      <td style="font-size:11.5px; color:var(--accent-amber); max-width:200px;">${escapeHtml(l.pitch_hook || 'Boutique Store Setup')}</td>
      <td style="max-width:300px;">
        <div style="font-size:11.5px; color:var(--text-muted); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">${escapeHtml(l.outreach_message || '—')}</div>
      </td>
      <td onclick="event.stopPropagation();">
        ${l.outreach_message ? `<button class="btn btn-sm btn-primary" onclick="copyPitchText('${escapeAttr(l.outreach_message)}')">📋 Copy</button>` : '—'}
      </td>
    </tr>
  `).join('');
}

async function fetchMilestoneM5() {
  const tbody = document.getElementById('m5-tbody');
  if (!tbody) return;

  const res = await fetch(`/api/leads?${buildQueryString({ limit: 100 })}`);
  const data = await res.json();
  const leads = data.leads || [];

  tbody.innerHTML = leads.map(l => {
    let lists = [];
    if (l.in_contact_first) lists.push('Contact First');
    if (l.in_contact_later) lists.push('Contact Later');
    if (l.in_mega_cold_calling) lists.push('Mega Cold Calling');
    if (l.in_manual_instagram) lists.push('Manual IG');

    return `
      <tr onclick="openLeadModal('${escapeJsString(l.lead_id)}')">
        <td style="font-weight:600; color:var(--text-main);">${escapeHtml(l.business_name || l.lead_id)}</td>
        <td><span class="badge ${getPriorityBadgeClass(l.outreach_priority)}">${escapeHtml(l.outreach_priority || 'CONTACT')}</span></td>
        <td><span class="badge ${l.in_master ? 'badge-high' : 'badge-low'}">${l.in_master ? 'In Master CSV' : 'Discovered'}</span></td>
        <td style="font-size:11.5px; color:var(--text-muted);">${lists.join(', ') || 'Standard List'}</td>
        <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-dim);">${formatDate(l.discovered_at)}</td>
        <td onclick="event.stopPropagation();">
          <button class="btn btn-sm" onclick="openLeadModal('${escapeJsString(l.lead_id)}')">Inspect</button>
        </td>
      </tr>
    `;
  }).join('');
}

/* --------------------------------------------------------------------------
   Needs Attention View
   -------------------------------------------------------------------------- */

async function fetchAttention() {
  try {
    const res = await fetch('/api/attention');
    const data = await res.json();
    const items = data.items || [];

    document.getElementById('attention-view-badge').textContent = `${items.length} Action Items`;

    const feed = document.getElementById('attention-full-feed');
    if (!feed) return;

    if (items.length === 0) {
      feed.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-dim);">All items resolved. No action required!</div>`;
      return;
    }

    feed.innerHTML = items.map(item => `
      <div class="timeline-item" onclick="openLeadModal('${escapeJsString(item.lead_id)}')">
        <div class="timeline-icon" style="color:var(--accent-red);">🚨</div>
        <div class="timeline-content">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span class="timeline-title">${escapeHtml(item.business_name || item.lead_id)}</span>
            <span class="badge badge-skip">${escapeHtml(item.type)}</span>
          </div>
          <div class="timeline-desc" style="color:var(--accent-amber);">${escapeHtml(item.reason)}</div>
          <div style="font-size:11px; color:var(--text-dim); margin-top:4px;">Action: ${escapeHtml(item.recommended_action)}</div>
        </div>
        <div onclick="event.stopPropagation();">
          <button class="btn btn-sm btn-primary" onclick="openLeadModal('${escapeJsString(item.lead_id)}')">Resolve ➔</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Attention error:', err);
  }
}

/* --------------------------------------------------------------------------
   Analytics View
   -------------------------------------------------------------------------- */

async function fetchAnalytics() {
  try {
    const res = await fetch(`/api/overview?${buildQueryString()}`);
    const data = await res.json();
    
    // Render Channel breakdown
    const chContainer = document.getElementById('analytics-channels');
    if (chContainer) {
      const channels = data.channels || {};
      const chList = Object.entries(channels);
      const chMax = Math.max(1, ...chList.map(e => e[1]));
      chContainer.innerHTML = chList.map(([k, v]) => `
        <div>
          <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
            <span style="color:var(--text-muted);">${k}</span>
            <span style="font-weight:700; color:var(--text-main);">${v}</span>
          </div>
          <div style="background:var(--bg-input); height:8px; border-radius:4px; overflow:hidden;">
            <div style="background:var(--primary-blue); width:${Math.round((v/chMax)*100)}%; height:100%;"></div>
          </div>
        </div>
      `).join('');
    }

    // Render Potential breakdown
    const potContainer = document.getElementById('analytics-potential');
    if (potContainer) {
      const pot = data.sales_potential_breakdown || {};
      const potList = [
        { label: 'HIGH POTENTIAL', count: pot.HIGH || 0, color: 'var(--accent-green)' },
        { label: 'MODERATE POTENTIAL', count: pot.MODERATE || 0, color: 'var(--accent-amber)' },
        { label: 'LOW POTENTIAL', count: pot.LOW || 0, color: 'var(--text-dim)' },
        { label: 'SKIP / ARCHIVE', count: pot.SKIP || 0, color: 'var(--accent-red)' },
      ];
      const potMax = Math.max(1, ...potList.map(p => p.count));
      potContainer.innerHTML = potList.map(p => `
        <div>
          <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
            <span style="color:var(--text-muted);">${p.label}</span>
            <span style="font-weight:700; color:var(--text-main);">${p.count}</span>
          </div>
          <div style="background:var(--bg-input); height:8px; border-radius:4px; overflow:hidden;">
            <div style="background:${p.color}; width:${Math.round((p.count/potMax)*100)}%; height:100%;"></div>
          </div>
        </div>
      `).join('');
    }

    // Render Cities
    const cityContainer = document.getElementById('analytics-cities');
    if (cityContainer) {
      const geo = data.geography || {};
      const entries = Object.entries(geo).sort((a, b) => b[1] - a[1]);
      const max = Math.max(1, ...entries.map(e => e[1]));
      cityContainer.innerHTML = entries.map(([city, count]) => `
        <div>
          <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px;">
            <span style="color:var(--text-muted);">${escapeHtml(city)}</span>
            <span style="font-weight:700; color:var(--text-main);">${count}</span>
          </div>
          <div style="background:var(--bg-input); height:8px; border-radius:4px; overflow:hidden;">
            <div style="background:var(--accent-insta); width:${Math.round((count/max)*100)}%; height:100%;"></div>
          </div>
        </div>
      `).join('');
    }

    // Render WA Health
    const waHealth = document.getElementById('analytics-wa-health');
    if (waHealth) {
      const wa = data.whatsapp_summary || {};
      const total = (wa.SENT || 0) + (wa.FAILED || 0) + (wa.PENDING || 0) + (wa.NO_WHATSAPP_NUMBER || 0) || 1;
      const sentPct = Math.round(((wa.SENT || 0) / total) * 100);
      const failPct = Math.round(((wa.FAILED || 0) / total) * 100);

      waHealth.innerHTML = `
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px;">
          <div class="kpi-card green" style="padding:10px;">
            <div style="font-size:11px; color:var(--text-muted);">Delivery Success</div>
            <div style="font-size:20px; font-weight:700; color:var(--accent-green);">${sentPct}%</div>
          </div>
          <div class="kpi-card red" style="padding:10px;">
            <div style="font-size:11px; color:var(--text-muted);">Failure Rate</div>
            <div style="font-size:20px; font-weight:700; color:var(--accent-red);">${failPct}%</div>
          </div>
        </div>
        <div style="font-size:11.5px; color:var(--text-muted);">
          Ground truth from <code style="color:var(--primary-blue);">output/m6_send_state.json</code>.
        </div>
      `;
    }
  } catch (err) {
    console.error('Analytics error:', err);
  }
}

/* --------------------------------------------------------------------------
   Data Sources & Files View
   -------------------------------------------------------------------------- */

async function fetchSources() {
  try {
    const res = await fetch('/api/sources');
    const data = await res.json();
    const files = data.files || [];

    document.getElementById('sources-count-badge').textContent = `${files.length} Pipeline Files Discovered`;

    const tbody = document.getElementById('sources-tbody');
    if (!tbody) return;

    if (files.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-dim);">No files discovered.</td></tr>`;
      return;
    }

    tbody.innerHTML = files.map(f => `
      <tr>
        <td>
          <div style="font-weight:600; color:var(--text-main); font-family:var(--font-mono); font-size:12px;">${escapeHtml(f.filename)}</div>
          <div style="font-size:11px; color:var(--text-dim);">${escapeHtml(f.relative_path)}</div>
        </td>
        <td><span class="badge ${getMilestoneBadgeClass(f.milestone)}">${escapeHtml(f.milestone)}</span></td>
        <td><span class="badge badge-low">${escapeHtml(f.file_type)}</span></td>
        <td style="font-family:var(--font-mono); font-size:11.5px;">${escapeHtml(f.size_display)}</td>
        <td style="font-family:var(--font-mono); font-weight:600; color:var(--primary-blue);">${f.record_count > 0 ? f.record_count : '—'}</td>
        <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-dim);">${formatTimestamp(f.modified_time)}</td>
        <td>
          <button class="btn btn-sm" onclick="openFilePreview('${escapeAttr(f.path)}')">👁 Preview</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Sources error:', err);
  }
}

/* --------------------------------------------------------------------------
   Lead Detail Modal (360° Drawer)
   -------------------------------------------------------------------------- */

async function openLeadModal(leadId, targetTab = 'tab-overview') {
  if (!leadId) return;
  State.activeLeadId = leadId;

  try {
    const res = await fetch(`/api/leads/${encodeURIComponent(leadId)}`);
    if (!res.ok) throw new Error('Failed to load lead details');
    const data = await res.json();
    const lead = data.lead;
    State.cachedLead = lead;

    // Header
    document.getElementById('modal-lead-title').textContent = lead.business_name || lead.lead_id;
    document.getElementById('modal-lead-subtitle').textContent = `Lead ID: ${lead.lead_id} • Discovered: ${formatDate(lead.discovered_at)}`;

    // Archive / Skip Alert Banner & Safety
    const isArch = Boolean(lead.is_archived || lead.sales_stage === 'ARCHIVED' || lead.outreach_priority === 'ARCHIVE' || lead.final_action === 'ARCHIVE');
    const isSkip = !isArch && Boolean(lead.sales_stage === 'SKIPPED' || lead.outreach_priority === 'SKIP' || lead.sales_potential === 'SKIP' || lead.final_action === 'SKIP' || (lead.is_skipped && lead.outreach_priority !== 'CONTACT FIRST' && lead.final_action !== 'CONTACT'));
    const alertBanner = document.getElementById('modal-lead-alert-banner');
    const reasonContainer = document.getElementById('md-archive-skip-container');
    const reasonEl = document.getElementById('md-archive-skip-reason');

    if (isArch) {
      if (alertBanner) {
        alertBanner.style.display = 'block';
        alertBanner.className = 'alert-banner alert-banner-archive';
        alertBanner.innerHTML = `<strong>📦 ARCHIVED LEAD</strong> — This lead has been archived (${escapeHtml(lead.archive_skip_reason || 'Archived in pipeline')}). WhatsApp execution is safely disabled.`;
      }
      if (reasonContainer && reasonEl) {
        reasonContainer.style.display = 'block';
        reasonEl.textContent = lead.archive_skip_reason || 'Archived in pipeline';
      }
    } else if (isSkip) {
      if (alertBanner) {
        alertBanner.style.display = 'block';
        alertBanner.className = 'alert-banner alert-banner-skip';
        alertBanner.innerHTML = `<strong>🚫 SKIPPED LEAD</strong> — This lead was skipped (${escapeHtml(lead.archive_skip_reason || 'Missing contact information or criteria')}). WhatsApp execution is safely disabled.`;
      }
      if (reasonContainer && reasonEl) {
        reasonContainer.style.display = 'block';
        reasonEl.textContent = lead.archive_skip_reason || 'Missing contact info / skipped';
      }
    } else {
      if (alertBanner) {
        alertBanner.style.display = 'none';
        alertBanner.innerHTML = '';
      }
      if (reasonContainer) {
        reasonContainer.style.display = 'none';
      }
    }

    // Tab 1: Overview
    const displayPriority = isArch ? 'ARCHIVE' : (isSkip ? 'SKIP' : (lead.outreach_priority || lead.final_action || 'CONTACT FIRST'));
    let displayStatus = isArch ? 'ARCHIVE' : (isSkip ? 'SKIP' : (lead.m6_status || lead.sales_stage || 'PENDING'));
    if (lead.m6_status === 'SKIPPED_LIMIT' && !isSkip && !isArch) {
      displayStatus = 'LIMIT REACHED (Next Batch)';
    }
    const scoreStr = (lead.qualification_score !== null && lead.qualification_score !== undefined) ? `${lead.qualification_score} / 100` : '—';

    document.getElementById('md-biz-name').textContent = lead.business_name || '—';
    document.getElementById('md-location').textContent = lead.location || lead.city || '—';
    document.getElementById('md-phone').textContent = lead.phone || 'None Found';
    document.getElementById('md-email').textContent = lead.email || 'None Found';
    
    const ovScore = document.getElementById('md-ov-score');
    if (ovScore) ovScore.textContent = scoreStr;

    document.getElementById('md-potential').innerHTML = `<span class="badge ${getPotentialBadgeClass(lead.sales_potential)}">${escapeHtml(lead.sales_potential || 'MOD')}</span>`;
    document.getElementById('md-priority').innerHTML = `<span class="badge ${getPriorityBadgeClass(displayPriority)}">${escapeHtml(displayPriority)}</span>`;
    document.getElementById('md-wa-status').innerHTML = `<span class="badge ${getStatusBadgeClass(displayStatus)}">${escapeHtml(displayStatus)}</span>`;

    // Render M1 to M5 Pipeline Stepper & Skip Reason Audit Box
    renderModalM1toM5Stepper(lead, isArch, isSkip, displayPriority);

    const ovHook = document.getElementById('md-ov-pitch-hook');
    if (ovHook) ovHook.textContent = lead.pitch_hook || lead.outreach_opening || lead.outreach_subject || '—';

    const ovOpp = document.getElementById('md-ov-opportunity');
    if (ovOpp) ovOpp.textContent = lead.opportunity || lead.detected_opportunity || lead.why_this_lead || '—';

    const ovGaps = document.getElementById('md-ov-gaps');
    if (ovGaps) ovGaps.textContent = lead.gaps || 'Manual WhatsApp & DM order management';

    // Initialize M7 Boutique Demo Generator for this lead
    const m7BizName = lead.business_name || lead.lead_id || '';
    const m7PreviewEl = document.getElementById('m7-demo-biz-name-preview');
    const m7TabBizEl = document.getElementById('m7-tab-biz-name');
    if (m7PreviewEl) m7PreviewEl.textContent = m7BizName || 'this lead';
    if (m7TabBizEl) m7TabBizEl.textContent = m7BizName || '—';

    // Reset demo ready state in modal
    State.currentDemoUrl = null;
    State.currentDemoWhatsAppMsg = null;
    const m7Unready = document.getElementById('m7-demo-unready');
    const m7Ready = document.getElementById('m7-demo-ready');
    const m7UrlDisp = document.getElementById('m7-demo-url-display');
    const m7WaBox = document.getElementById('m7-wa-preview-box');
    const m7TabUrlDisp = document.getElementById('m7-tab-demo-url-display');
    const m7TabOpenBtn = document.getElementById('btn-tab-open-demo');
    const m7TabCopyBtn = document.getElementById('btn-tab-copy-link');
    const m7TabPrepBtn = document.getElementById('btn-tab-prepare-wa');
    const m7TabWaBox = document.getElementById('m7-tab-wa-box');

    if (m7Unready) m7Unready.style.display = 'block';
    if (m7Ready) m7Ready.style.display = 'none';
    if (m7UrlDisp) m7UrlDisp.textContent = '--';
    if (m7WaBox) m7WaBox.style.display = 'none';
    if (m7TabUrlDisp) m7TabUrlDisp.textContent = 'Click "Generate Demo" to build URL';
    if (m7TabOpenBtn) m7TabOpenBtn.style.display = 'none';
    if (m7TabCopyBtn) m7TabCopyBtn.style.display = 'none';
    if (m7TabPrepBtn) m7TabPrepBtn.style.display = 'none';
    if (m7TabWaBox) m7TabWaBox.style.display = 'none';

    if (targetTab === 'tab-demo') {
      setTimeout(() => handleGenerateDemoClick(lead), 50);
    }

    // Quick Action Buttons on Overview Tab
    const quickActions = document.getElementById('modal-quick-actions');
    const phoneNum = lead.m6_recipient || lead.phone || '';
    const cleanNum = phoneNum.replace(/[^0-9]/g, '');
    const pitch = lead.outreach_message || 'Assalam o Alaikum! I came across your business...';

    if (quickActions) {
      let actionsHtml = '';
      if (lead.phone) {
        actionsHtml += `<a href="tel:${escapeAttr(lead.phone)}" class="btn btn-sm btn-primary">📞 Call Phone</a>`;
      }
      if (lead.outreach_message) {
        actionsHtml += `<button class="btn btn-sm" onclick="copyCurrentPitch()">📋 Copy Pitch Hook</button>`;
      }
      actionsHtml += `<button class="btn btn-sm" onclick="handleGenerateDemoClick()" style="background:rgba(212,175,55,0.15); border:1px solid rgba(212,175,55,0.4); color:#D4AF37; font-weight:600;">🚀 Generate Demo</button>`;
      if (!isArch && !isSkip && cleanNum) {
        actionsHtml += `
          <a href="https://wa.me/${cleanNum}?text=${encodeURIComponent(pitch)}" target="_blank" class="btn btn-sm" style="background:var(--accent-wa); border-color:var(--accent-wa); color:#fff;">
            💬 Open WhatsApp
          </a>
        `;
      }
      actionsHtml += `<button class="btn btn-sm" onclick="switchModalTab('tab-outreach')">✉️ View Full Pitch</button>`;
      actionsHtml += `<button class="btn btn-sm" onclick="switchModalTab('tab-research')">🔬 View Tech Audit</button>`;
      quickActions.innerHTML = actionsHtml;
    }

    // Tab 2: Research
    document.getElementById('md-website').innerHTML = lead.website ? `<a href="${escapeAttr(lead.website)}" target="_blank" style="color:var(--primary-blue);">🌐 ${escapeHtml(lead.website)}</a>` : 'No dedicated website';
    document.getElementById('md-instagram').innerHTML = lead.instagram ? `<a href="https://instagram.com/${lead.instagram.replace(/^@/, '')}" target="_blank" style="color:var(--accent-insta);">📸 @${escapeHtml(lead.instagram)}</a>` : 'No Instagram';
    document.getElementById('md-facebook').textContent = lead.facebook || 'None Found';
    document.getElementById('md-tiktok').textContent = lead.tiktok || 'None Found';
    document.getElementById('md-gaps').textContent = lead.gaps || 'Manual WhatsApp & DM order management';
    document.getElementById('md-opportunity').textContent = lead.opportunity || 'High conversion opportunity for custom online store and video ads.';

    // Tab 3: Qualification
    document.getElementById('md-score').textContent = scoreStr;
    document.getElementById('md-qual-status').textContent = lead.qualification_status || (isArch ? 'ARCHIVED' : (isSkip ? 'SKIPPED' : 'QUALIFIED'));
    document.getElementById('md-service').textContent = lead.primary_service || 'E-Commerce Store & Ads Growth';
    document.getElementById('md-rec-action').textContent = lead.recommended_action || displayPriority;
    document.getElementById('md-qual-reason').textContent = lead.archive_skip_reason || lead.qualification_reasons || 'Lead exhibits active social presence with high e-commerce potential.';

    // Tab 4: Outreach
    document.getElementById('md-pitch-box').textContent = pitch;
    document.getElementById('md-pitch-angle').textContent = lead.pitch_hook || 'Boutique Automation Pitch';
    document.getElementById('md-pitch-words').textContent = `${pitch.split(/\s+/).length} words`;

    // Tab 5: Master
    document.getElementById('md-master-action').textContent = displayPriority;
    let lists = [];
    if (lead.in_master) lists.push('Master Sales Leads');
    if (lead.in_contact_first) lists.push('Contact First');
    if (lead.in_contact_later) lists.push('Contact Later');
    if (lead.in_mega_cold_calling) lists.push('Mega Cold Calling');
    if (lead.in_manual_instagram) lists.push('Manual Instagram DMs');
    if (isArch) lists.push('Archive Repository');
    if (isSkip) lists.push('Skipped Queue');
    document.getElementById('md-list-membership').textContent = lists.join(', ') || 'Standard Registry';
    document.getElementById('md-master-notes').textContent = lead.archive_skip_reason || lead.notes || (isArch || isSkip ? 'Preserved for audit & historical intelligence.' : 'Ready for automated or manual outreach.');

    // Tab 6: Delivery
    document.getElementById('md-m6-status').innerHTML = `<span class="badge ${getStatusBadgeClass(displayStatus)}">${escapeHtml(displayStatus)}</span>`;
    const modalEditM6 = document.getElementById('modal-edit-m6-status');
    if (modalEditM6) {
      modalEditM6.value = lead.m6_status || displayStatus || 'PENDING';
    }
    document.getElementById('md-m6-recipient').textContent = lead.m6_recipient || lead.phone || '—';
    document.getElementById('md-m6-sent-at').textContent = formatTimestamp(lead.m6_sent_at || lead.last_contacted_at);
    document.getElementById('md-m6-attempts').textContent = `${lead.m6_send_attempts || 0} attempts`;
    document.getElementById('md-m6-error').textContent = lead.m6_error || lead.archive_skip_reason || 'No errors reported.';

    const waBtnContainer = document.getElementById('modal-wa-btn-container');

    if (isArch || isSkip) {
      waBtnContainer.innerHTML = `
        <div style="padding:10px 14px; background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); border-radius:6px; font-size:12px; color:#fca5a5;">
          🔒 <strong>Pipeline Safety Lock:</strong> Automated and direct WhatsApp outreach is disabled for ${isArch ? 'Archived' : 'Skipped'} leads (${escapeHtml(lead.archive_skip_reason || 'Inactive status')}).
        </div>
      `;
    } else if (cleanNum) {
      waBtnContainer.innerHTML = `
        <a href="https://wa.me/${cleanNum}?text=${encodeURIComponent(pitch)}" target="_blank" class="btn btn-primary" style="background:var(--accent-wa); border-color:var(--accent-wa);">
          💬 Open WhatsApp with Pre-filled Pitch
        </a>
      `;
    } else {
      waBtnContainer.innerHTML = `<span style="font-size:11.5px; color:var(--text-dim);">No phone number available for direct WhatsApp opener.</span>`;
    }

    // Tab 7: History & Provenance
    const provContainer = document.getElementById('md-provenance-list');
    const provFiles = lead.source_files || [];
    if (provFiles.length === 0) {
      provContainer.innerHTML = `<div style="color:var(--text-dim); font-size:12px;">No source file provenance tracked.</div>`;
    } else {
      provContainer.innerHTML = provFiles.map(pf => `
        <div class="timeline-item">
          <div class="timeline-icon">📁</div>
          <div class="timeline-content">
            <div class="timeline-title">${escapeHtml(pf.split('/').pop())}</div>
            <div class="timeline-desc" style="font-family:var(--font-mono);">${escapeHtml(pf)}</div>
          </div>
        </div>
      `).join('');
    }

    // Populate CRM & Sales Activity Data for Modal
    populateModalCRM(lead);

    // Switch to target tab (defaults to tab-overview)
    switchModalTab(targetTab || 'tab-overview');

    // Show modal
    document.getElementById('lead-modal').classList.add('active');
  } catch (err) {
    console.error('Lead detail error:', err);
    showToast('Failed to open lead details', 'error');
  }
}

function renderModalM1toM5Stepper(lead, isArch, isSkip, displayPriority) {
  // Step M1: Discovery
  const m1Badge = document.getElementById('step-m1-badge');
  const m1Desc = document.getElementById('step-m1-desc');
  if (m1Badge) {
    m1Badge.className = 'badge badge-sent';
    m1Badge.textContent = 'DONE';
  }
  if (m1Desc) {
    m1Desc.textContent = lead.city || 'Discovered';
  }

  // Step M2: Research
  const m2Badge = document.getElementById('step-m2-badge');
  const m2Desc = document.getElementById('step-m2-desc');
  const hasWeb = Boolean(lead.website);
  if (m2Badge) {
    if (lead.website_reachable === 'unreachable' || lead.website_status === 'unreachable') {
      m2Badge.className = 'badge badge-failed';
      m2Badge.textContent = 'UNREACHABLE';
    } else if (hasWeb) {
      m2Badge.className = 'badge badge-sent';
      m2Badge.textContent = 'RESEARCHED';
    } else if (lead.instagram) {
      m2Badge.className = 'badge badge-connected';
      m2Badge.textContent = 'INSTAGRAM';
    } else {
      m2Badge.className = 'badge badge-low';
      m2Badge.textContent = 'LOCAL ONLY';
    }
  }
  if (m2Desc) {
    m2Desc.textContent = hasWeb ? (lead.ecommerce_status === 'present' ? 'E-Comm Found' : 'Site Audited') : (lead.instagram ? 'Social Found' : 'No Website');
  }

  // Step M3: Qualification
  const m3Badge = document.getElementById('step-m3-badge');
  const m3Desc = document.getElementById('step-m3-desc');
  const scoreVal = lead.qualification_score !== null && lead.qualification_score !== undefined ? lead.qualification_score : null;
  if (m3Badge) {
    if (scoreVal !== null) {
      m3Badge.className = scoreVal >= 60 ? 'badge badge-interested' : (scoreVal >= 30 ? 'badge badge-send' : 'badge badge-low');
      m3Badge.textContent = `${scoreVal}/100`;
    } else {
      m3Badge.className = 'badge badge-low';
      m3Badge.textContent = 'EVALUATED';
    }
  }
  if (m3Desc) {
    m3Desc.textContent = lead.qualification_status || (scoreVal && scoreVal >= 50 ? 'Passed' : 'Reviewed');
  }

  // Step M4: Outreach
  const m4Badge = document.getElementById('step-m4-badge');
  const m4Desc = document.getElementById('step-m4-desc');
  const hasPitch = Boolean(lead.outreach_message && lead.outreach_message.trim().length > 30);
  if (m4Badge) {
    if (hasPitch) {
      m4Badge.className = 'badge badge-sent';
      m4Badge.textContent = 'PITCH READY';
    } else if (isArch || isSkip) {
      m4Badge.className = 'badge badge-skip';
      m4Badge.textContent = 'SKIPPED';
    } else {
      m4Badge.className = 'badge badge-low';
      m4Badge.textContent = 'DRAFT';
    }
  }
  if (m4Desc) {
    m4Desc.textContent = hasPitch ? (lead.outreach_channel || 'WhatsApp') : (isArch ? 'Disqualified' : 'Skipped');
  }

  // Step M5: Final Routing
  const m5Badge = document.getElementById('step-m5-badge');
  const m5Desc = document.getElementById('step-m5-desc');
  if (m5Badge) {
    m5Badge.className = `badge ${getPriorityBadgeClass(displayPriority)}`;
    m5Badge.textContent = displayPriority;
  }
  if (m5Desc) {
    m5Desc.textContent = isArch ? 'Archived' : (isSkip ? 'Skipped' : (displayPriority === 'CONTACT FIRST' ? 'Top Priority' : 'Secondary'));
  }

  // Decision & Reason Box
  const decisionBox = document.getElementById('modal-journey-decision-box');
  if (decisionBox) {
    decisionBox.style.display = 'block';
    if (isArch) {
      decisionBox.className = 'journey-decision-box journey-box-archive';
      decisionBox.innerHTML = `
        <div style="font-weight:700; color:#f59e0b; display:flex; align-items:center; gap:8px;">
          <span>📦 M5 DECISION: ARCHIVED LEAD</span>
          <span class="badge badge-archive" style="font-size:10px;">ARCHIVE</span>
        </div>
        <div style="margin-top:6px; color:var(--text-main); font-size:12px; line-height:1.5;">
          <strong>Why it was Archived:</strong> ${escapeHtml(lead.archive_skip_reason || lead.review_reason || 'Archived during qualification stage.')}
        </div>
        <div style="margin-top:6px; font-size:11px; color:var(--text-dim);">
          🔒 <em>This lead is preserved in the system for historical audit. Automated outreach was stopped at M5 because sales potential or service fit was not met. Click the tabs above to see full details of M1 through M5.</em>
        </div>
      `;
    } else if (isSkip) {
      decisionBox.className = 'journey-decision-box journey-box-skip';
      decisionBox.innerHTML = `
        <div style="font-weight:700; color:#ef4444; display:flex; align-items:center; gap:8px;">
          <span>🚫 M5 DECISION: SKIPPED LEAD</span>
          <span class="badge badge-skip" style="font-size:10px;">SKIP</span>
        </div>
        <div style="margin-top:6px; color:var(--text-main); font-size:12px; line-height:1.5;">
          <strong>Why it was Skipped:</strong> ${escapeHtml(lead.archive_skip_reason || lead.review_reason || 'Missing required contact info or criteria.')}
        </div>
        <div style="margin-top:6px; font-size:11px; color:var(--text-dim);">
          💡 <em>Lead skipped in outreach queue. Click the <strong>Research (M2)</strong> or <strong>Qualification (M3)</strong> tabs above to audit full signals.</em>
        </div>
      `;
    } else if (displayPriority === 'CONTACT FIRST') {
      decisionBox.className = 'journey-decision-box journey-box-contact-first';
      decisionBox.innerHTML = `
        <div style="font-weight:700; color:#10b981; display:flex; align-items:center; gap:8px;">
          <span>🔥 M5 DECISION: CONTACT FIRST (Top Priority Qualified Lead)</span>
          <span class="badge badge-contact-first" style="font-size:10px;">ACTIVE</span>
        </div>
        <div style="margin-top:6px; color:var(--text-main); font-size:12px; line-height:1.5;">
          <strong>Opportunity / Why Qualified:</strong> ${escapeHtml(lead.opportunity || lead.why_this_lead || 'High sales potential with verified contact and clear growth opportunity.')}
        </div>
        ${lead.gaps ? `<div style="margin-top:4px; font-size:11.5px; color:var(--text-muted);"><strong>Identified Gap:</strong> ${escapeHtml(lead.gaps)}</div>` : ''}
      `;
    } else {
      decisionBox.className = 'journey-decision-box journey-box-contact-later';
      decisionBox.innerHTML = `
        <div style="font-weight:700; color:#38bdf8; display:flex; align-items:center; gap:8px;">
          <span>⏳ M5 DECISION: CONTACT LATER (Secondary Priority)</span>
          <span class="badge badge-contact-later" style="font-size:10px;">BATCH LATER</span>
        </div>
        <div style="margin-top:6px; color:var(--text-main); font-size:12px; line-height:1.5;">
          <strong>Status:</strong> ${escapeHtml(lead.opportunity || lead.why_this_lead || 'Queued for secondary follow-up.')}
        </div>
      `;
    }
  }
}

function closeLeadModal() {
  document.getElementById('lead-modal').classList.remove('active');
  State.activeLeadId = null;
  State.cachedLead = null;
}

function switchModalTab(tabId) {
  document.querySelectorAll('.modal-tab').forEach(t => {
    if (t.getAttribute('data-tab') === tabId) {
      t.classList.add('active');
    } else {
      t.classList.remove('active');
    }
  });

  document.querySelectorAll('.modal-tab-content').forEach(c => {
    c.style.display = 'none';
  });

  const activeContent = document.getElementById(tabId);
  if (activeContent) {
    activeContent.style.display = 'block';
  }
}

function copyCurrentPitch() {
  if (State.cachedLead && State.cachedLead.outreach_message) {
    copyPitchText(State.cachedLead.outreach_message);
  } else {
    showToast('No outreach pitch available for this lead', 'warning');
  }
}

/* --------------------------------------------------------------------------
   Milestone 7 (M7) — Personalized Boutique Demo Generator (Isolated)
   -------------------------------------------------------------------------- */

const M7_MASTER_DEMO_BASE = "https://website-demo-five-navy.vercel.app/";

function generatePersonalizedDemoUrl(businessName) {
  if (!businessName || typeof businessName !== 'string' || !businessName.trim()) {
    throw new Error('A valid, non-empty business name is required to generate a personalized demo URL.');
  }
  const cleanName = businessName.trim();
  const brand = encodeURIComponent(cleanName);
  const title = encodeURIComponent(`${cleanName} | Online Store`);
  return `${M7_MASTER_DEMO_BASE}?brand=${brand}&title=${title}`;
}

function buildDemoWhatsAppMessage(businessName, demoUrl) {
  const cleanBrand = (businessName || '').trim() || 'Brand';
  return (
    `Assalam o Alaikum ${cleanBrand} Team! 🌸\n\n` +
    `Main Haider from MalikAxiom Technology Lahore.\n\n` +
    `Aapka Instagram dekha — collection kaafi classy hai 👌 Is liye ${cleanBrand} ke naam se ek live premium storefront demo specially prepare kiya hai 👇🔥\n\n` +
    `🔗 ${demoUrl}\n\n` +
    `🤖 24/7 AI Brand Assistant — aapke brand se related customers ke har tarah ke questions ka jawab de sakta hai, including products, prices, sizes, fabric, delivery & more.\n\n` +
    `🛒 Seamless WhatsApp Ordering — product, size & color select karke direct order.\n\n` +
    `🎨 12+ Premium Themes — Themes button se apne logo/brand color ke saath live matching try karein.\n\n` +
    `💰 Complete setup starting from PKR 10,000\n\n` +
    `✨ Yeh sirf ek sample demo hai — design, colors aur layout aapki brand identity ke mutabiq fully customize ho sakta hai. Hamare paas aur bhi luxury layouts available hain.\n\n` +
    `Aapko concept kaisa laga? Agar aap kahen to main aapke saath complete features & setup share kar doon. 🤝\n\n` +
    `MalikAxiom Technology\n` +
    `🌐 malikaxiomtech.com`
  );
}

function handleGenerateDemoClick(leadOverride) {
  const lead = leadOverride || State.cachedLead;
  if (!lead) {
    showToast('No lead selected. Please select a lead first.', 'warning');
    return;
  }

  const rawName = lead.business_name || '';
  if (!rawName || typeof rawName !== 'string' || !rawName.trim()) {
    showToast('Cannot generate demo: Lead is missing a valid business name.', 'error');
    return;
  }

  try {
    const demoUrl = generatePersonalizedDemoUrl(rawName);
    const waMsg = buildDemoWhatsAppMessage(rawName, demoUrl);

    State.currentDemoUrl = demoUrl;
    State.currentDemoBizName = rawName.trim();
    State.currentDemoWhatsAppMsg = waMsg;

    // 1. Update Overview Tab Section Elements
    const unreadyEl = document.getElementById('m7-demo-unready');
    const readyEl = document.getElementById('m7-demo-ready');
    const urlDisplay = document.getElementById('m7-demo-url-display');
    const waMsgText = document.getElementById('m7-wa-message-text');

    if (unreadyEl) unreadyEl.style.display = 'none';
    if (readyEl) readyEl.style.display = 'block';
    if (urlDisplay) urlDisplay.textContent = demoUrl;
    if (waMsgText) waMsgText.textContent = waMsg;

    // 2. Update Dedicated Tab-demo Elements
    const tabUrlDisplay = document.getElementById('m7-tab-demo-url-display');
    const tabOpenBtn = document.getElementById('btn-tab-open-demo');
    const tabCopyBtn = document.getElementById('btn-tab-copy-link');
    const tabPrepBtn = document.getElementById('btn-tab-prepare-wa');
    const tabWaMsgText = document.getElementById('m7-tab-wa-text');

    if (tabUrlDisplay) tabUrlDisplay.textContent = demoUrl;
    if (tabOpenBtn) tabOpenBtn.style.display = 'inline-block';
    if (tabCopyBtn) tabCopyBtn.style.display = 'inline-block';
    if (tabPrepBtn) tabPrepBtn.style.display = 'inline-block';
    if (tabWaMsgText) tabWaMsgText.textContent = waMsg;

    // 3. Setup Direct WhatsApp Links (Direct web.whatsapp.com to prevent api.whatsapp.com emoji corruption)
    const phoneNum = lead.m6_recipient || lead.phone || '';
    const cleanNum = phoneNum.replace(/[^0-9]/g, '');
    const waDirectLink = document.getElementById('m7-wa-direct-link');
    const tabWaDirectLink = document.getElementById('m7-tab-wa-link');
    const waDraftHref = cleanNum 
      ? `https://web.whatsapp.com/send?phone=${cleanNum}&text=${encodeURIComponent(waMsg)}`
      : `https://web.whatsapp.com/send?text=${encodeURIComponent(waMsg)}`;

    const onLaunchDraft = () => {
      copyPitchText(waMsg);
      showToast('✓ WhatsApp opened & message copied! (Press Cmd+V / Ctrl+V in chat to paste with full emojis)', 'success');
    };

    if (waDirectLink) {
      waDirectLink.href = waDraftHref;
      waDirectLink.onclick = onLaunchDraft;
    }
    if (tabWaDirectLink) {
      tabWaDirectLink.href = waDraftHref;
      tabWaDirectLink.onclick = onLaunchDraft;
    }

    showToast('🚀 Personalized Boutique Demo Ready!', 'success');
  } catch (err) {
    console.error('M7 demo generation error:', err);
    showToast(err.message || 'Failed to generate demo URL', 'error');
  }
}

function handleOpenDemoClick() {
  if (!State.currentDemoUrl) {
    showToast('Please click "Generate Demo" first.', 'warning');
    return;
  }
  window.open(State.currentDemoUrl, '_blank');
}

function handleCopyDemoLinkClick() {
  if (!State.currentDemoUrl) {
    showToast('Please click "Generate Demo" first.', 'warning');
    return;
  }
  copyPitchText(State.currentDemoUrl);
  showToast('✓ Boutique Demo link copied to clipboard!', 'success');
}

function handleToggleWhatsAppDemoClick() {
  const waBox = document.getElementById('m7-wa-preview-box');
  const tabWaBox = document.getElementById('m7-tab-wa-box');
  if (waBox) {
    waBox.style.display = waBox.style.display === 'none' ? 'block' : 'none';
  }
  if (tabWaBox) {
    tabWaBox.style.display = tabWaBox.style.display === 'none' ? 'block' : 'none';
  }
}

function handleCopyDemoWhatsAppClick() {
  if (!State.currentDemoWhatsAppMsg) {
    showToast('Please generate the demo message first.', 'warning');
    return;
  }
  copyPitchText(State.currentDemoWhatsAppMsg);
  showToast('✓ Prepared WhatsApp outreach text copied!', 'success');
}

/* --------------------------------------------------------------------------
   File Preview Modal
   -------------------------------------------------------------------------- */

async function openFilePreview(filePath) {
  if (!filePath) return;

  const modal = document.getElementById('file-preview-modal');
  const loading = document.getElementById('preview-loading');
  const csvContainer = document.getElementById('preview-csv-container');
  const codeContainer = document.getElementById('preview-code-container');
  const codeContent = document.getElementById('preview-code-content');
  const title = document.getElementById('preview-file-title');
  const pathLabel = document.getElementById('preview-file-path');

  title.textContent = filePath.split('/').pop();
  pathLabel.textContent = filePath;

  loading.style.display = 'block';
  csvContainer.style.display = 'none';
  codeContainer.style.display = 'none';
  modal.classList.add('active');

  try {
    const res = await fetch(`/api/sources/preview?path=${encodeURIComponent(filePath)}`);
    if (!res.ok) throw new Error('Failed to preview file');
    const data = await res.json();

    loading.style.display = 'none';

    if (data.file_type === 'CSV' && data.headers) {
      csvContainer.style.display = 'block';
      const thead = document.getElementById('preview-csv-thead');
      const tbody = document.getElementById('preview-csv-tbody');

      thead.innerHTML = `<tr>${data.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')}</tr>`;
      tbody.innerHTML = (data.rows || []).map(row => `
        <tr>${data.headers.map(h => `<td>${escapeHtml(row[h] || '')}</td>`).join('')}</tr>
      `).join('');
    } else if (data.raw_json) {
      codeContainer.style.display = 'block';
      codeContent.textContent = JSON.stringify(data.raw_json, null, 2);
    } else if (data.lines) {
      codeContainer.style.display = 'block';
      codeContent.textContent = data.lines.join('\n');
    }
  } catch (err) {
    console.error('File preview error:', err);
    loading.textContent = `Failed to preview file: ${err.message}`;
  }
}

function closePreviewModal() {
  document.getElementById('file-preview-modal').classList.remove('active');
}

/* --------------------------------------------------------------------------
   Export & Copy Helpers
   -------------------------------------------------------------------------- */

function copyPitchText(text) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast('Outreach pitch copied to clipboard! 📋', 'success');
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast('Outreach pitch copied to clipboard! 📋', 'success');
  });
}

function exportCurrentLeadsCSV() {
  const extraParams = {
    limit: 2000,
    page: 1,
    tab: State.leadsTab,
    priority: State.leadsFilter.priority,
    potential: State.leadsFilter.potential,
    channel: State.leadsFilter.channel,
    status: State.leadsFilter.status,
    milestone: State.leadsFilter.milestone,
    city: State.leadsFilter.city,
    call_status: State.leadsFilter.call_status,
    category: State.leadsFilter.category,
    activity: State.leadsFilter.activity,
    sort_by: State.leadsFilter.sort_by,
  };

  const url = `/api/leads?${buildQueryString(extraParams)}`;
  fetch(url).then(r => r.json()).then(data => {
    const leads = data.leads || [];
    if (leads.length === 0) {
      showToast('No leads match the current filters to export', 'warning');
      return;
    }

    const headers = [
      'lead_id',
      'business_name',
      'phone',
      'whatsapp',
      'email',
      'city',
      'discovered_at',
      'last_called_at',
      'call_status',
      'category',
      'sales_potential',
      'outreach_priority',
      'outreach_channel',
      'm6_status',
      'primary_service',
      'opportunity',
      'pitch_hook',
      'outreach_message',
    ];

    const csvRows = [headers.join(',')];

    leads.forEach(l => {
      const row = headers.map(h => {
        let val = l[h] || '';
        val = String(val).replace(/"/g, '""');
        return `"${val}"`;
      });
      csvRows.push(row.join(','));
    });

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    const dateSuffix = State.customStart || State.dateFilter.toLowerCase();
    link.download = `malikaxiom_leads_${dateSuffix}_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    showToast(`Exported ${leads.length} leads to CSV successfully! 📥`, 'success');
  }).catch(err => {
    console.error('Export error:', err);
    showToast('Failed to export leads', 'error');
  });
}

/* --------------------------------------------------------------------------
   Auto-Refresh & Toast Notifications
   -------------------------------------------------------------------------- */

function initAutoRefresh() {
  // Background polling every 15 seconds
  State.pollInterval = setInterval(() => {
    if (!document.hidden && !State.refreshing) {
      fetchOverview();
      loadViewData(State.currentView);
    }
  }, 15000);
}

async function triggerManualRefresh() {
  if (State.refreshing) return;
  State.refreshing = true;

  const icon = document.getElementById('refresh-icon');
  if (icon) icon.style.transform = 'rotate(360deg)';

  try {
    const res = await fetch('/api/refresh', { method: 'POST' });
    const data = await res.json();
    showToast(`Refreshed! ${data.total_leads} leads indexed across ${data.total_files} files.`, 'success');
    refreshAll();
  } catch (err) {
    showToast('Refresh failed', 'error');
  } finally {
    State.refreshing = false;
    if (icon) icon.style.transform = 'none';
  }
}

function refreshAll() {
  fetchOverview();
  fetchCrmMetrics();
  loadViewData(State.currentView);
}

function startSidebarClock() {
  const clockEl = document.getElementById('sidebar-clock');
  function update() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  update();
  setInterval(update, 1000);
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.style.cssText = `
    background-color: var(--bg-sidebar);
    border: 1px solid var(--border-highlight);
    border-radius: 6px;
    padding: 10px 14px;
    color: var(--text-main);
    font-size: 12px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    gap: 8px;
    animation: fadeIn 0.2s ease;
  `;

  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  if (type === 'warning') icon = '⚠️';
  if (type === 'error') icon = '❌';

  toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* --------------------------------------------------------------------------
   UI Badges & Formatting Helpers
   -------------------------------------------------------------------------- */

function getPotentialBadgeClass(p) {
  const up = (p || '').toUpperCase();
  if (up === 'HIGH') return 'badge-high';
  if (up === 'MODERATE') return 'badge-mod';
  if (up === 'LOW') return 'badge-low';
  return 'badge-skip';
}

function getPriorityBadgeClass(p) {
  const up = (p || '').toUpperCase();
  if (up === 'CONTACT FIRST') return 'badge-high';
  if (up === 'CONTACT LATER') return 'badge-mod';
  if (up === 'ARCHIVE' || up === 'ARCHIVED') return 'badge-archive';
  if (up === 'SKIP' || up === 'SKIPPED') return 'badge-skip';
  return 'badge-low';
}

function getStatusBadgeClass(s) {
  const up = (s || '').toUpperCase();
  if (up === 'SENT') return 'badge-sent';
  if (up === 'FAILED') return 'badge-failed';
  if (up === 'PENDING') return 'badge-pending';
  if (up === 'SKIPPED_LIMIT' || up.includes('LIMIT')) return 'badge-mod';
  if (up === 'NO_WHATSAPP_NUMBER') return 'badge-no-wa';
  if (up === 'AWAITING_MANUAL_SEND') return 'badge-mod';
  if (up === 'ARCHIVE' || up === 'ARCHIVED') return 'badge-archive';
  if (up === 'SKIP' || up === 'SKIPPED') return 'badge-skip';
  if (up === 'NOT_READY') return 'badge-not-ready';
  return 'badge-low';
}

function getChannelBadgeClass(c) {
  const up = (c || '').toUpperCase();
  if (up.includes('INSTAGRAM')) return 'badge-insta';
  if (up.includes('WHATSAPP')) return 'badge-wa';
  if (up.includes('CALL')) return 'badge-high';
  return 'badge-low';
}

function getMilestoneBadgeClass(m) {
  const up = (m || '').toUpperCase();
  if (up.includes('M6') || up.includes('WHATSAPP')) return 'badge-sent';
  if (up.includes('M5') || up.includes('MASTER')) return 'badge-high';
  if (up.includes('M4') || up.includes('OUTREACH')) return 'badge-mod';
  if (up.includes('M3') || up.includes('QUAL')) return 'badge-mod';
  if (up.includes('M2') || up.includes('RESEARCH')) return 'badge-low';
  return 'badge-low';
}

function getMilestoneIcon(m) {
  const up = (m || '').toUpperCase();
  if (up.includes('M6') || up.includes('WHATSAPP')) return '💬';
  if (up.includes('M5')) return '🗄️';
  if (up.includes('M4')) return '✉️';
  if (up.includes('M3')) return '⚖️';
  if (up.includes('M2')) return '🔬';
  return '📥';
}

function formatDate(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr.slice(0, 10);
    return d.toISOString().slice(0, 10);
  } catch (e) {
    return isoStr.slice(0, 10);
  }
}

function formatTimestamp(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return isoStr;
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeAttr(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, '\\n').replace(/\r/g, '');
}

function escapeJsString(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '');
}

function initModals() {
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeLeadModal();
      closePreviewModal();
      closeQuickCallModal();
    }
  });

  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('active');
        if (modal.id === 'modal-quick-call') {
          modal.style.display = 'none';
        }
      }
    });
  });
}

/* --------------------------------------------------------------------------
   Milestone 7 (M7) — Sales Activity & Call CRM Engine
   -------------------------------------------------------------------------- */

function getCrmCallBadgeClass(status) {
  const s = (status || '').toUpperCase();
  if (s === 'CONNECTED') return 'badge-connected';
  if (s === 'NOT_CONNECTED') return 'badge-not-connected';
  return 'badge-call-pending';
}

function getCrmCategoryBadgeClass(category) {
  const c = (category || '').toUpperCase();
  if (c === 'INTERESTED') return 'badge-interested';
  if (c === 'SEND') return 'badge-send';
  if (c === 'NO_ANSWER') return 'badge-no-answer';
  return 'badge-low';
}

function getCategoryDisplay(category) {
  const c = (category || '').toUpperCase();
  if (c === 'INTERESTED') return 'A — INTERESTED';
  if (c === 'SEND') return 'B — SEND';
  if (c === 'NO_ANSWER') return 'C — NO ANSWER';
  return category || '—';
}

function formatRelativeTime(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = d.toDateString() === yesterday.toDateString();
    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (isToday) return `Today, ${timeStr}`;
    if (isYesterday) return `Yesterday, ${timeStr}`;
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + `, ${timeStr}`;
  } catch (e) {
    return isoStr;
  }
}

async function fetchCrmMetrics() {
  try {
    const res = await fetch('/api/crm/metrics');
    if (!res.ok) return;
    const data = await res.json();
    State.crmMetrics = data;
    renderCrmMetrics(data);
    fetchTodayCrmFeed();
  } catch (err) {
    console.error('CRM metrics error:', err);
  }
}

function renderCrmMetrics(data) {
  if (!data) return;
  const today = data.today || {};
  const total = data.total || {};

  const setEl = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = (val || 0).toLocaleString();
  };

  // Today CRM Metrics
  setEl('crm-today-calls', today.calls_made);
  setEl('crm-today-connected', today.connected);
  setEl('crm-today-not-connected', today.not_connected);
  setEl('crm-today-interested', today.interested);
  setEl('crm-today-send', today.send);
  setEl('crm-today-no-answer', today.no_answer);

  // Total CRM Metrics
  setEl('crm-total-leads', total.total_leads);
  setEl('crm-total-pending', total.pending_calls);
  setEl('crm-total-calls', total.calls_made);
  setEl('crm-total-connected', total.connected);
  setEl('crm-total-not-connected', total.not_connected);
  setEl('crm-total-interested', total.interested);
  setEl('crm-total-send', total.send);
  setEl('crm-total-no-answer', total.no_answer);

  // Sidebar Pending Calls Badge
  const pendingBadge = document.getElementById('badge-crm-pending');
  if (pendingBadge) {
    pendingBadge.textContent = `${total.pending_calls || 0} PENDING`;
  }
}

async function fetchTodayCrmFeed() {
  const feedContainer = document.getElementById('crm-today-activity-feed');
  const feedCount = document.getElementById('crm-today-feed-count');
  if (!feedContainer) return;

  try {
    const res = await fetch('/api/crm/activities?limit=15&today_only=true');
    if (!res.ok) return;
    const data = await res.json();
    const activities = data.activities || [];

    if (feedCount) {
      feedCount.textContent = `${activities.length} recorded events today`;
    }

    if (activities.length === 0) {
      feedContainer.innerHTML = `<div style="font-size:11.5px; color:var(--text-dim); padding:6px 0;">No call activities logged today yet. Click "Call Done" on any lead to record.</div>`;
      return;
    }

    feedContainer.innerHTML = activities.map(item => {
      const timeStr = formatRelativeTime(item.timestamp);
      const callStatus = item.call_status || '';
      const category = item.category || '';
      return `
        <div class="timeline-item" onclick="openLeadModal('${escapeJsString(item.lead_id)}', 'tab-activity')" style="cursor:pointer; display:flex; justify-content:space-between; align-items:center; padding:5px 8px; background:var(--bg-input); border-radius:5px; border:1px solid var(--border-color); font-size:11.5px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-weight:600; color:var(--text-main);">${escapeHtml(item.business_name || item.lead_id)}</span>
            ${callStatus ? `<span class="badge ${getCrmCallBadgeClass(callStatus)}" style="font-size:10px;">${escapeHtml(callStatus)}</span>` : ''}
            ${category ? `<span class="badge ${getCrmCategoryBadgeClass(category)}" style="font-size:10px;">${escapeHtml(getCategoryDisplay(category))}</span>` : ''}
            ${item.note ? `<span style="color:var(--text-muted); font-style:italic; max-width:260px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">"${escapeHtml(item.note)}"</span>` : ''}
          </div>
          <div style="font-size:10.5px; color:var(--text-dim); font-family:var(--font-mono); white-space:nowrap;">${timeStr}</div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Error fetching today activity feed:', err);
  }
}

function openQuickCallModal(leadId) {
  let lead = State.leadsMap ? State.leadsMap.get(leadId) : null;
  if (!lead && State.cachedLead && State.cachedLead.lead_id === leadId) {
    lead = State.cachedLead;
  }
  if (!lead && State.currentLeads) {
    lead = State.currentLeads.find(x => x.lead_id === leadId);
  }
  if (!lead) {
    lead = { lead_id: leadId };
  }
  openQuickCallModalFromData(lead);
}

function openQuickCallModalFromData(leadData) {
  let lead = leadData;
  if (typeof leadData === 'string') {
    try {
      lead = JSON.parse(leadData);
    } catch (e) {
      console.error('Failed to parse lead data for quick call:', e);
      return;
    }
  }
  if (!lead) return;

  const modal = document.getElementById('modal-quick-call');
  if (!modal) return;

  document.getElementById('qc-lead-id').value = lead.lead_id || '';
  document.getElementById('qc-business-name').textContent = lead.business_name || lead.lead_id || 'Unknown Lead';
  document.getElementById('qc-phone-number').textContent = lead.phone ? `📞 ${lead.phone}` : 'No Direct Phone';
  document.getElementById('qc-note-input').value = lead.latest_note || '';

  const qcM6 = document.getElementById('qc-m6-status');
  if (qcM6) {
    qcM6.value = lead.m6_status || '';
  }

  const currentStatus = lead.call_status === 'NOT_CONNECTED' ? 'NOT_CONNECTED' : 'CONNECTED';
  selectQuickCallStatus(currentStatus);
  selectQuickCategory(lead.category || '');

  modal.style.display = 'flex';
  modal.classList.add('active');
}

function openQuickCallFromModal() {
  if (State.cachedLead && State.cachedLead.lead_id) {
    openQuickCallModal(State.cachedLead.lead_id);
  } else if (State.activeLeadId) {
    openQuickCallModal(State.activeLeadId);
  }
}

function closeQuickCallModal() {
  const modal = document.getElementById('modal-quick-call');
  if (modal) {
    modal.style.display = 'none';
    modal.classList.remove('active');
  }
}

function selectQuickCallStatus(status) {
  document.getElementById('qc-selected-call-status').value = status;
  const btnConn = document.getElementById('qc-btn-connected');
  const btnNotConn = document.getElementById('qc-btn-not-connected');

  if (btnConn) {
    if (status === 'CONNECTED') {
      btnConn.style.background = '#059669';
      btnConn.style.borderColor = '#10b981';
      btnConn.style.color = '#fff';
      btnConn.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.4)';
    } else {
      btnConn.style.background = 'var(--bg-input)';
      btnConn.style.borderColor = 'var(--border-color)';
      btnConn.style.color = 'var(--text-muted)';
      btnConn.style.boxShadow = 'none';
    }
  }

  if (btnNotConn) {
    if (status === 'NOT_CONNECTED') {
      btnNotConn.style.background = '#dc2626';
      btnNotConn.style.borderColor = '#ef4444';
      btnNotConn.style.color = '#fff';
      btnNotConn.style.boxShadow = '0 0 10px rgba(239, 68, 68, 0.4)';
    } else {
      btnNotConn.style.background = 'var(--bg-input)';
      btnNotConn.style.borderColor = 'var(--border-color)';
      btnNotConn.style.color = 'var(--text-muted)';
      btnNotConn.style.boxShadow = 'none';
    }
  }
}

function selectQuickCategory(cat) {
  document.getElementById('qc-selected-category').value = cat;
  const btnInt = document.getElementById('qc-btn-cat-interested');
  const btnSend = document.getElementById('qc-btn-cat-send');
  const btnNoAns = document.getElementById('qc-btn-cat-no-answer');

  const setBtnStyle = (btn, isActive, activeBg, activeBorder, activeColor, activeShadow) => {
    if (!btn) return;
    if (isActive) {
      btn.style.background = activeBg;
      btn.style.borderColor = activeBorder;
      btn.style.color = activeColor;
      btn.style.boxShadow = activeShadow;
    } else {
      btn.style.background = 'var(--bg-input)';
      btn.style.borderColor = 'var(--border-color)';
      btn.style.color = 'var(--text-muted)';
      btn.style.boxShadow = 'none';
    }
  };

  setBtnStyle(btnInt, cat === 'INTERESTED', '#0284c7', '#38bdf8', '#fff', '0 0 8px rgba(56, 189, 248, 0.4)');
  setBtnStyle(btnSend, cat === 'SEND', '#9333ea', '#c084fc', '#fff', '0 0 8px rgba(192, 132, 252, 0.4)');
  setBtnStyle(btnNoAns, cat === 'NO_ANSWER', '#ea580c', '#fb923c', '#fff', '0 0 8px rgba(251, 146, 60, 0.4)');
}

function setQuickNote(text) {
  const input = document.getElementById('qc-note-input');
  if (input) {
    if (input.value && !input.value.endsWith(' ') && !input.value.endsWith('.')) {
      input.value += '; ' + text;
    } else if (input.value && input.value.endsWith('.')) {
      input.value += ' ' + text;
    } else {
      input.value = text;
    }
    input.focus();
  }
}

async function saveQuickCall() {
  const leadId = document.getElementById('qc-lead-id').value;
  const callStatus = document.getElementById('qc-selected-call-status').value || 'CONNECTED';
  const category = document.getElementById('qc-selected-category').value || '';
  const note = document.getElementById('qc-note-input').value.trim();
  const m6Select = document.getElementById('qc-m6-status');
  const m6Status = m6Select ? m6Select.value : '';

  if (!leadId) {
    showToast('No lead selected', 'error');
    return;
  }

  const saveBtn = document.getElementById('qc-btn-save');
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
  }

  try {
    const payload = {
      lead_id: leadId,
      call_status: callStatus,
      category: category,
      note: note
    };
    if (m6Status) {
      payload.m6_status = m6Status;
    }

    const res = await fetch('/api/crm/quick-call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to save call outcome');

    closeQuickCallModal();
    showToast(`✓ Call outcome saved: ${callStatus}${category ? ' • ' + getCategoryDisplay(category) : ''}`, 'success');

    // If modal is currently open for this lead, refresh its details
    if (State.activeLeadId === leadId) {
      const detailRes = await fetch(`/api/leads/${encodeURIComponent(leadId)}`);
      if (detailRes.ok) {
        const detailData = await detailRes.json();
        State.cachedLead = detailData.lead;
        populateModalCRM(detailData.lead);
      }
    }

    refreshAll();
  } catch (err) {
    console.error('Save quick call error:', err);
    showToast(err.message || 'Failed to save call outcome', 'error');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = '💾 Save Call Activity';
    }
  }
}

async function quickRowCallStatus(leadId, callStatus) {
  try {
    const res = await fetch('/api/crm/quick-call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_id: leadId, call_status: callStatus })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to update call status');
    showToast(`✓ Call status updated: ${callStatus}`, 'success');
    refreshAll();
  } catch (err) {
    console.error('Quick row call status error:', err);
    showToast('Failed to update call status', 'error');
  }
}

async function quickRowCategory(leadId, category) {
  try {
    const res = await fetch('/api/crm/activity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_id: leadId, category: category, action: 'CATEGORY_SELECT' })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to update category');
    showToast(`✓ Category updated: ${getCategoryDisplay(category)}`, 'success');
    refreshAll();
  } catch (err) {
    console.error('Quick row category error:', err);
    showToast('Failed to update category', 'error');
  }
}

async function quickChangeM6Status(leadId, newStatus) {
  if (!leadId) return;
  try {
    const res = await fetch('/api/crm/m6-status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_id: leadId, m6_status: newStatus })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to update M6 status');
    showToast(`✓ M6 status updated: ${newStatus}`, 'success');
    refreshAll();
  } catch (err) {
    console.error('Quick change M6 status error:', err);
    showToast('Failed to update M6 status', 'error');
  }
}

async function saveModalM6Status() {
  const leadId = State.activeLeadId || (State.cachedLead ? State.cachedLead.lead_id : null);
  if (!leadId) {
    showToast('No lead currently open', 'warning');
    return;
  }
  const selectEl = document.getElementById('modal-edit-m6-status');
  if (!selectEl) return;
  const newStatus = selectEl.value;

  try {
    const res = await fetch('/api/crm/m6-status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_id: leadId, m6_status: newStatus })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to update M6 status');
    showToast(`✓ M6 status updated: ${newStatus}`, 'success');

    const displayBadge = document.getElementById('md-m6-status');
    if (displayBadge) {
      displayBadge.innerHTML = `<span class="badge ${getStatusBadgeClass(newStatus)}">${escapeHtml(newStatus)}</span>`;
    }
    const ovBadge = document.getElementById('md-wa-status');
    if (ovBadge) {
      ovBadge.innerHTML = `<span class="badge ${getStatusBadgeClass(newStatus)}">${escapeHtml(newStatus)}</span>`;
    }

    const detailRes = await fetch(`/api/leads/${encodeURIComponent(leadId)}`);
    if (detailRes.ok) {
      const detailData = await detailRes.json();
      State.cachedLead = detailData.lead;
    }
    refreshAll();
  } catch (err) {
    console.error('Save modal M6 status error:', err);
    showToast('Failed to save M6 status', 'error');
  }
}

async function quickLogLeadActivity(callStatus, category) {
  if (!State.activeLeadId) return;
  try {
    const payload = { lead_id: State.activeLeadId };
    if (callStatus) payload.call_status = callStatus;
    if (category) payload.category = category;

    const res = await fetch('/api/crm/quick-call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to log activity');
    showToast('✓ Activity logged successfully', 'success');

    // Reload lead in modal
    const detailRes = await fetch(`/api/leads/${encodeURIComponent(State.activeLeadId)}`);
    if (detailRes.ok) {
      const detailData = await detailRes.json();
      State.cachedLead = detailData.lead;
      populateModalCRM(detailData.lead);
    }
    refreshAll();
  } catch (err) {
    console.error('Quick log activity error:', err);
    showToast('Failed to log activity', 'error');
  }
}

async function submitModalActivityNote() {
  if (!State.activeLeadId) return;
  const statusEl = document.getElementById('modal-add-call-status');
  const catEl = document.getElementById('modal-add-category');
  const noteEl = document.getElementById('modal-new-note-text');

  const callStatus = statusEl ? statusEl.value : '';
  const category = catEl ? catEl.value : '';
  const note = noteEl ? noteEl.value.trim() : '';

  if (!note && !callStatus && !category) {
    showToast('Please enter a note or select an outcome', 'warning');
    return;
  }

  try {
    const payload = {
      lead_id: State.activeLeadId,
      action: 'NOTE_ADDED'
    };
    if (callStatus) payload.call_status = callStatus;
    if (category) payload.category = category;
    if (note) payload.note = note;

    const res = await fetch('/api/crm/activity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to save note');

    if (noteEl) noteEl.value = '';
    showToast('✓ Activity note saved (history preserved)!', 'success');

    // Reload lead in modal
    const detailRes = await fetch(`/api/leads/${encodeURIComponent(State.activeLeadId)}`);
    if (detailRes.ok) {
      const detailData = await detailRes.json();
      State.cachedLead = detailData.lead;
      populateModalCRM(detailData.lead);
    }
    refreshAll();
  } catch (err) {
    console.error('Submit activity note error:', err);
    showToast('Failed to save activity note', 'error');
  }
}

function populateModalCRM(lead) {
  if (!lead) return;
  const callStatus = lead.call_status || 'PENDING';
  const crmCategory = lead.category || '';
  const lastCalledStr = lead.last_called_at ? formatRelativeTime(lead.last_called_at) : 'Never Called';
  const history = lead.activity_history || [];
  const noteText = lead.latest_note || 'No notes recorded yet.';

  const setBadge = (id, html) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  };

  const setText = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  // Overview Tab CRM fields
  setBadge('md-crm-call-status', `<span class="badge ${getCrmCallBadgeClass(callStatus)}">${escapeHtml(callStatus)}</span>`);
  setBadge('md-crm-category', `<span class="badge ${getCrmCategoryBadgeClass(crmCategory)}">${escapeHtml(crmCategory ? getCategoryDisplay(crmCategory) : '—')}</span>`);
  setText('md-crm-last-called', lastCalledStr);
  setText('md-crm-count', `${history.length} recorded events`);
  setText('md-crm-latest-note', noteText);

  // Dedicated Tab 9 CRM fields
  setBadge('md-tab-crm-call-status', `<span class="badge ${getCrmCallBadgeClass(callStatus)}">${escapeHtml(callStatus)}</span>`);
  setBadge('md-tab-crm-category', `<span class="badge ${getCrmCategoryBadgeClass(crmCategory)}">${escapeHtml(crmCategory ? getCategoryDisplay(crmCategory) : '—')}</span>`);
  setText('md-tab-crm-last-called', lastCalledStr);
  setText('md-tab-crm-count', `${history.length}`);
  setText('md-tab-crm-latest-note', noteText);

  // Tab 9 Historical stream
  const histList = document.getElementById('md-crm-history-list');
  if (histList) {
    if (history.length === 0) {
      histList.innerHTML = `<div style="text-align:center; padding:18px; color:var(--text-dim); font-size:12px;">No activity logged yet for this lead. Use the form above to add notes or outcomes.</div>`;
    } else {
      const reversed = [...history].reverse();
      histList.innerHTML = reversed.map(item => {
        const timeStr = formatRelativeTime(item.timestamp);
        const itemCallStatus = item.call_status || '';
        const itemCat = item.category || '';
        return `
          <div class="timeline-item" style="padding:10px 12px; background:var(--bg-input); border-radius:6px; border:1px solid var(--border-color); display:flex; flex-direction:column; gap:4px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <div style="display:flex; align-items:center; gap:6px;">
                ${itemCallStatus ? `<span class="badge ${getCrmCallBadgeClass(itemCallStatus)}" style="font-size:10px;">${escapeHtml(itemCallStatus)}</span>` : ''}
                ${itemCat ? `<span class="badge ${getCrmCategoryBadgeClass(itemCat)}" style="font-size:10px;">${escapeHtml(getCategoryDisplay(itemCat))}</span>` : ''}
                <span style="font-size:10px; color:var(--text-dim); text-transform:uppercase; font-weight:600;">${escapeHtml(item.action || 'ACTIVITY')}</span>
              </div>
              <span style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${timeStr}</span>
            </div>
            ${item.note ? `<div style="font-size:12px; color:var(--text-main); font-style:italic; margin-top:2px;">"${escapeHtml(item.note)}"</div>` : ''}
          </div>
        `;
      }).join('');
    }
  }
}

function filterLeadsByCallStatus(callStatus) {
  switchView('leads');
  State.leadsFilter.call_status = callStatus;
  const el = document.getElementById('filter-lead-call-status');
  if (el) el.value = callStatus;
  State.leadsPage = 1;
  fetchMasterLeads();
}

function filterLeadsByCategory(category) {
  switchView('leads');
  State.leadsFilter.category = category;
  const el = document.getElementById('filter-lead-category');
  if (el) el.value = category;
  State.leadsPage = 1;
  fetchMasterLeads();
}

function filterLeadsByActivity(act) {
  switchView('leads');
  State.leadsFilter.activity = act;
  const el = document.getElementById('filter-lead-activity');
  if (el) el.value = act;
  State.leadsPage = 1;
  fetchMasterLeads();
}

function filterLeadsByCallAndCategory(callStatus, category) {
  switchView('leads');
  if (callStatus !== undefined) {
    State.leadsFilter.call_status = callStatus;
    const el = document.getElementById('filter-lead-call-status');
    if (el) el.value = callStatus;
  }
  if (category !== undefined) {
    State.leadsFilter.category = category;
    const el = document.getElementById('filter-lead-category');
    if (el) el.value = category;
  }
  State.leadsPage = 1;
  fetchMasterLeads();
}
