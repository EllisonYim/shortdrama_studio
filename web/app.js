let mode = 'topic';
let projectId = null;
let currentTab = 'input';
let isScriptEditing = false;
let selectedRatio = '16:9';
let selectedResolution = '1080p';

const tabs = ['input', 'script', 'characters', 'scenes', 'storyboard', 'prompts', 'images', 'videos', 'output'];
const views = {
  input: 'view-input',
  script: 'view-script',
  characters: 'view-characters',
  scenes: 'view-scenes',
  storyboard: 'view-storyboard',
  prompts: 'view-prompts',
  images: 'view-images',
  videos: 'view-videos',
  output: 'view-output'
};

// DOM Elements
const topicInputs = document.getElementById('topicInputs');
const scriptInputs = document.getElementById('scriptInputs');
const createBtn = document.getElementById('createBtn');
const createStatus = document.getElementById('createStatus');
const statusEl = document.getElementById('status');
const statusDot = document.getElementById('status-dot');
const historyList = document.getElementById('history-list');

const btnScriptModeText = document.getElementById('btnScriptModeText');
const btnScriptModeFile = document.getElementById('btnScriptModeFile');
const scriptInputTextContainer = document.getElementById('scriptInputTextContainer');
const scriptInputFileContainer = document.getElementById('scriptInputFileContainer');
const scriptFileInput = document.getElementById('scriptFileInput');
const fileNameDisplay = document.getElementById('fileName');

// Script View Elements
const outScript = document.getElementById('outScript');
const scriptLoading = document.getElementById('scriptLoading');
const btnEditScript = document.getElementById('btnEditScript');
const btnOptimizeScript = document.getElementById('btnOptimizeScript');
const btnSaveScript = document.getElementById('btnSaveScript');
const btnNextToCharacters = document.getElementById('btnNextToCharacters');
const btnNextToScenes = document.getElementById('btnNextToScenes');
const btnNextToStoryboard = document.getElementById('btnNextToStoryboard');
const btnNextToPrompts = document.getElementById('btnNextToPrompts');
const btnNextToImages = document.getElementById('btnNextToImages');
const btnNextToVideos = document.getElementById('btnNextToVideos');

// Storyboard View Elements
const storyboardList = document.getElementById('storyboardList');
const storyboardEmpty = document.getElementById('storyboardEmpty');
const btnGenStoryboard = document.getElementById('btnGenStoryboard');
const btnSaveStoryboard = document.getElementById('btnSaveStoryboard');

// Character & Scene Elements
const charList = document.getElementById('charList');
const charEmpty = document.getElementById('charEmpty');
const btnGenChars = document.getElementById('btnGenChars');
const btnGenCharPrompts = document.getElementById('btnGenCharPrompts');
const btnGenCharImages = document.getElementById('btnGenCharImages');
const charLoading = document.getElementById('charLoading');

const sceneList = document.getElementById('sceneList');
const sceneEmpty = document.getElementById('sceneEmpty');
const btnGenScenes = document.getElementById('btnGenScenes');
const btnGenScenePrompts = document.getElementById('btnGenScenePrompts');
const btnGenSceneImages = document.getElementById('btnGenSceneImages');
const sceneLoading = document.getElementById('sceneLoading');

// Other View Elements
const promptsList = document.getElementById('promptsList');
const btnGenPrompts = document.getElementById('btnGenPrompts');
const globalImgCount = document.getElementById('globalImgCount');
const imgZoomModal = document.getElementById('imgZoomModal');
const imgZoomContent = document.getElementById('imgZoomContent');
const btnSavePrompts = document.getElementById('btnSavePrompts');
const imagesEl = document.getElementById('images');
const btnGenImages = document.getElementById('btnGenImages');
const videosEl = document.getElementById('videos');
const btnGenVideos = document.getElementById('btnGenVideos');
const finalVideoEl = document.getElementById('finalVideo');
const btnMerge = document.getElementById('btnMerge');

// Loading Elements
const storyboardLoading = document.getElementById('storyboardLoading');
const promptsLoading = document.getElementById('promptsLoading');
const imagesLoading = document.getElementById('imagesLoading');
const videosLoading = document.getElementById('videosLoading');

// Settings Elements
const settingsModal = document.getElementById('settingsModal');
const settingsBtn = document.getElementById('settingsBtn');
const closeSettings = document.getElementById('closeSettings');
const cancelSettings = document.getElementById('cancelSettings');
const saveSettings = document.getElementById('saveSettings');

// Logs Elements
const logsModal = document.getElementById('logsModal');
const logsBtn = document.getElementById('logsBtn');
const closeLogs = document.getElementById('closeLogs');
const logsContent = document.getElementById('logsContent');
const refreshLogsBtn = document.getElementById('refreshLogsBtn');
const logLevelFilter = document.getElementById('logLevelFilter');

// Project Details Elements
const projectDetailsModal = document.getElementById('projectDetailsModal');
const pdName = document.getElementById('pd_name');
const pdId = document.getElementById('pd_id');
const pdCreated = document.getElementById('pd_created');
const pdStatus = document.getElementById('pd_status');
const pdPlatform = document.getElementById('pd_platform');
const pdCurrentStage = document.getElementById('pd_current_stage');
const pdUpdated = document.getElementById('pd_updated');

const STEP_NAMES = ["剧本创作", "角色设计", "场景设计", "分镜生成", "提示词生成", "分镜首图", "分镜视频", "视频拼接", "已完成"];
const STEP_TABS = ["script", "characters", "scenes", "storyboard", "prompts", "images", "videos", "videos", "output"];

const pdTokens = document.getElementById('pd_tokens');
const pdVideoDuration = document.getElementById('pd_video_duration');
const pdProjectDuration = document.getElementById('pd_project_duration');
const pdShots = document.getElementById('pd_shots_count');
const pdImages = document.getElementById('pd_images_count');
const pdVideos = document.getElementById('pd_videos_count');
const closeProjectDetails = document.getElementById('closeProjectDetails');
const btnOpenProject = document.getElementById('btnOpenProject');
const btnDeleteProject = document.getElementById('btnDeleteProject');
const processingScenes = new Set();

// Helper to escape HTML
function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Helper to normalize paths
function normalizePath(path) {
    if (!path) return '';
    
    // Check for TOS URL (Volcengine / BytePlus)
    // Use proxy for TOS to handle private buckets and CORS
    if (path.includes('.volces.com') || path.includes('.bytepluses.com') || path.includes('tos-')) {
        // If already signed (has query params), might work directly, but proxy is safer for CORS
        return `/api/proxy/tos?url=${encodeURIComponent(path)}`;
    }
    
    if (path.startsWith('http') || path.startsWith('blob:')) return path;
    
    // If path contains 'data/', normalize to serve from static mount
    const idx = path.indexOf('data/');
    if (idx !== -1) {
        return '/' + path.substring(idx);
    }
    
    return path.startsWith('/') ? path : '/' + path;
}

// Global Button State Control
function setInteractionState(enabled) {
    // isGenerating = !enabled; // If you want to track global state
    const buttons = [
        createBtn, btnEditScript, btnOptimizeScript, btnSaveScript,
        btnGenStoryboard, btnSaveStoryboard, btnGenPrompts, btnSavePrompts,
        btnGenImages, btnGenVideos, btnMerge,
        btnNextToStoryboard, btnNextToPrompts, btnNextToImages, btnNextToVideos
    ];
    
    buttons.forEach(btn => {
        if (btn) {
            btn.disabled = !enabled;
            if (!enabled) {
                btn.classList.add('opacity-50', 'cursor-not-allowed');
            } else {
                btn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        }
    });
}

// Init
function init() {
  loadHistory();
  setupEventListeners();
  loadProjectConfig();
  switchTab('input');
}

function setupEventListeners() {
  // Resolution & Ratio Selectors - Moved to loadProjectConfig -> renderVisualSettings
  // setupVisualSettings(); 

  // Mode Switch
  document.querySelectorAll('input[name="mode"]').forEach(r => {
    r.addEventListener('change', (e) => {
      mode = e.target.value;
      if (mode === 'topic') {
        topicInputs.classList.remove('hidden');
        scriptInputs.classList.add('hidden');
      } else {
        topicInputs.classList.add('hidden');
        scriptInputs.classList.remove('hidden');
      }
    });
  });

  // Project Details Actions
  closeProjectDetails.addEventListener('click', () => projectDetailsModal.classList.add('hidden'));
  btnOpenProject.addEventListener('click', () => {
      if (currentDetailId) {
          loadProject(currentDetailId);
          projectDetailsModal.classList.add('hidden');
      }
  });
  btnDeleteProject.addEventListener('click', deleteProject);

  // Script Input Mode Toggle
  btnScriptModeText.addEventListener('click', () => {
      btnScriptModeText.className = 'px-4 py-2 rounded-lg bg-blue-100 text-blue-700 font-medium';
      btnScriptModeFile.className = 'px-4 py-2 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 font-medium transition-colors';
      scriptInputTextContainer.classList.remove('hidden');
      scriptInputFileContainer.classList.add('hidden');
  });

  btnScriptModeFile.addEventListener('click', () => {
      btnScriptModeFile.className = 'px-4 py-2 rounded-lg bg-blue-100 text-blue-700 font-medium';
      btnScriptModeText.className = 'px-4 py-2 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 font-medium transition-colors';
      scriptInputFileContainer.classList.remove('hidden');
      scriptInputTextContainer.classList.add('hidden');
  });

  // File Upload Logic
  scriptFileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) {
          fileNameDisplay.textContent = `已选择: ${file.name}`;
          const reader = new FileReader();
          reader.onload = (e) => {
              document.getElementById('scriptTextInput').value = e.target.result;
          };
          reader.readAsText(file);
      }
  });

  // Image Zoom Close
  imgZoomModal.addEventListener('click', () => {
      imgZoomModal.classList.remove('opacity-100');
      setTimeout(() => imgZoomModal.classList.add('hidden'), 300);
  });
  
  // Prevent zoom close when clicking the image itself
  imgZoomContent.addEventListener('click', (e) => {
      e.stopPropagation();
  });

  // Create Project
  createBtn.addEventListener('click', createProject);

  // Script Actions
  btnEditScript.addEventListener('click', toggleScriptEdit);
  btnSaveScript.addEventListener('click', saveScriptContent);
  btnOptimizeScript.addEventListener('click', optimizeScript);
  if (btnNextToCharacters) btnNextToCharacters.addEventListener('click', () => callStep('characters'));
  if (btnNextToScenes) btnNextToScenes.addEventListener('click', () => callStep('scenes'));
  if (btnNextToStoryboard) btnNextToStoryboard.addEventListener('click', () => callStep('storyboard'));
  if (btnNextToPrompts) btnNextToPrompts.addEventListener('click', () => callStep('prompts'));
  if (btnNextToImages) btnNextToImages.addEventListener('click', () => callStep('images'));
  if (btnNextToVideos) btnNextToVideos.addEventListener('click', () => callStep('videos'));

  // Character Actions
  if (btnGenChars) btnGenChars.addEventListener('click', () => callStep('characters'));
  if (btnGenCharPrompts) btnGenCharPrompts.addEventListener('click', () => callStep('characters/prompts'));
  if (btnGenCharImages) btnGenCharImages.addEventListener('click', () => callStep('characters/images'));

  // Scene Actions
  if (btnGenScenes) btnGenScenes.addEventListener('click', () => callStep('scenes'));
  if (btnGenScenePrompts) btnGenScenePrompts.addEventListener('click', () => callStep('scenes/prompts'));
  if (btnGenSceneImages) btnGenSceneImages.addEventListener('click', () => callStep('scenes/images'));

  // Storyboard Actions
  btnGenStoryboard.addEventListener('click', () => callStep('storyboard'));
  if (btnSaveStoryboard) btnSaveStoryboard.addEventListener('click', saveStoryboard);

  // Other Generation Buttons
  btnGenPrompts.addEventListener('click', () => callStep('prompts'));
  if (btnSavePrompts) btnSavePrompts.addEventListener('click', savePromptsData);
  btnGenImages.addEventListener('click', () => callStep('images', { image_count: parseInt(globalImgCount.value) || 1 }));
  btnGenVideos.addEventListener('click', () => callStep('videos'));
  btnMerge.addEventListener('click', () => callStep('merge'));

  // Tab Switching (Top Nav)
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-${t}`);
    if (btn) {
      btn.addEventListener('click', () => switchTab(t));
    }
  });

  // Sidebar Steps Switching
  document.querySelectorAll('#steps button').forEach(btn => {
    btn.addEventListener('click', () => {
      const step = btn.dataset.step;
      if (step === 'merge') switchTab('output');
      else switchTab(step);
    });
  });

  // Settings
  settingsBtn.addEventListener('click', openSettings);
  closeSettings.addEventListener('click', () => settingsModal.classList.add('hidden'));
  cancelSettings.addEventListener('click', () => settingsModal.classList.add('hidden'));
  saveSettings.addEventListener('click', saveConfig);
  
  // Platform Switch
  const platformSelect = document.getElementById('conf_platform');
  if (platformSelect) {
      platformSelect.addEventListener('change', (e) => {
          if (typeof renderPlatformSettings === 'function') {
              renderPlatformSettings(e.target.value);
          }
      });
  }

  // Logs
  if (logsBtn) logsBtn.addEventListener('click', () => {
      logsModal.classList.remove('hidden');
      loadLogs();
  });
  if (closeLogs) closeLogs.addEventListener('click', () => logsModal.classList.add('hidden'));
  if (refreshLogsBtn) refreshLogsBtn.addEventListener('click', loadLogs);
  if (logLevelFilter) logLevelFilter.addEventListener('change', loadLogs);
}

async function loadProjectConfig() {
    try {
        const res = await fetch('/api/config');
        const conf = await res.json();
        const appConf = conf.app || {};
        
        // Populate Styles
        const scriptStyles = appConf.script_styles || [];
        const visualStyles = appConf.visual_styles || [];
        
        const styleSelect = document.getElementById('style');
        if (styleSelect) {
            styleSelect.innerHTML = scriptStyles.map(s => `<option>${s}</option>`).join('');
        }
        
        const vsSelect = document.getElementById('visualStyle');
        if (vsSelect) {
            vsSelect.innerHTML = visualStyles.map(s => `<option>${s}</option>`).join('');
        }
        
        const vsScriptSelect = document.getElementById('visualStyleScript');
        if (vsScriptSelect) {
            vsScriptSelect.innerHTML = visualStyles.map(s => `<option>${s}</option>`).join('');
        }

        // Populate Ratios and Resolutions
        const ratios = appConf.aspect_ratios || ["16:9", "9:16"];
        const resolutions = appConf.resolutions || ["1080p"];
        
        renderVisualSettings(ratios, resolutions);

    } catch(e) {
        console.error("Failed to load config", e);
        // Fallback to default render if failed? 
        // Currently existing HTML has defaults, but we might have cleared them or rely on replacement.
        // If we rely on replacement, we should probably manually trigger default render here if fetch fails.
        // But for now, let's assume it works.
        setupVisualSettings(); // Fallback to setup listeners on existing elements
    }
}

function renderVisualSettings(ratios, resolutions) {
    const ratioContainer = document.getElementById('aspectRatioSelector');
    const resContainer = document.getElementById('resolutionSelector');
    
    // Ratios
    if (ratioContainer) {
        ratioContainer.innerHTML = ratios.map(r => {
            const [w, h] = r.split(':').map(Number);
            
            // Calculate normalized width/height fitting in a 24px box
            const MAX_SIZE = 24;
            const scale = MAX_SIZE / Math.max(w, h);
            const finalW = w * scale;
            const finalH = h * scale;
            
            return `
             <button type="button" data-value="${r}" class="ratio-btn px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-500 hover:text-blue-600 hover:border-blue-200 text-sm font-medium transition-all flex flex-col items-center gap-1 min-w-[70px]">
                <div class="w-[24px] h-[24px] flex items-center justify-center">
                    <span style="width: ${finalW}px; height: ${finalH}px;" class="border-2 border-current rounded-[2px] opacity-50 block"></span>
                </div>
                ${r}
             </button>
            `;
        }).join('');
    }

    // Resolutions
    if (resContainer) {
        resContainer.innerHTML = resolutions.map(r => `
            <button type="button" data-value="${r}" class="res-btn px-6 py-2 rounded-md text-sm font-medium text-gray-500 hover:text-gray-900 transition-all">${r}</button>
        `).join('');
    }
    
    setupVisualSettings();
}

// Visual Settings Logic
function setupVisualSettings() {
    const ratioBtns = document.querySelectorAll('.ratio-btn');
    const resBtns = document.querySelectorAll('.res-btn');

    function updateRatioUI() {
        ratioBtns.forEach(btn => {
            if (btn.dataset.value === selectedRatio) {
                btn.className = 'ratio-btn px-4 py-2 rounded-lg bg-white border-2 border-slate-800 text-slate-900 shadow-md text-sm font-bold transition-all flex flex-col items-center gap-1 min-w-[70px] scale-105';
                btn.querySelector('span').classList.remove('opacity-50');
            } else {
                btn.className = 'ratio-btn px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-400 hover:text-blue-600 hover:border-blue-200 text-sm font-medium transition-all flex flex-col items-center gap-1 min-w-[70px]';
                btn.querySelector('span').classList.add('opacity-50');
            }
        });
    }

    function updateResUI() {
        resBtns.forEach(btn => {
            if (btn.dataset.value === selectedResolution) {
                btn.className = 'res-btn px-6 py-2 rounded-md text-sm font-bold bg-white text-slate-900 shadow-sm transition-all';
            } else {
                btn.className = 'res-btn px-6 py-2 rounded-md text-sm font-medium text-gray-500 hover:text-gray-900 transition-all';
            }
        });
    }

    ratioBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            selectedRatio = btn.dataset.value;
            updateRatioUI();
        });
    });

    resBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            selectedResolution = btn.dataset.value;
            updateResUI();
        });
    });

    // Init defaults
    updateRatioUI();
    updateResUI();
}

// Tab Logic
function switchTab(tabName) {
  currentTab = tabName;
  
  // Hide all views
  Object.values(views).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
  });

  // Show active view
  const activeViewId = views[tabName];
  if (activeViewId) {
    document.getElementById(activeViewId).classList.remove('hidden');
  }

  // Update Top Nav Styles
  tabs.forEach(t => {
    const btn = document.getElementById(`tab-${t}`);
    if (btn) {
      if (t === tabName) {
        btn.className = 'px-4 py-1.5 rounded-md text-sm font-medium bg-gray-900 text-white shadow-sm transition-all';
      } else {
        btn.className = 'px-4 py-1.5 rounded-md text-sm font-medium text-gray-500 hover:text-gray-900 transition-all';
      }
    }
  });

  // Update Sidebar Styles
  const sidebarStep = tabName === 'output' ? 'merge' : tabName;
  document.querySelectorAll('#steps button').forEach(btn => {
    // Reset classes
    btn.className = 'w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-blue-600 transition-all duration-200 flex items-center group';
    const icon = btn.querySelector('span');
    if (icon) icon.className = 'w-6 h-6 mr-3 flex items-center justify-center rounded-md bg-gray-100 text-gray-500 group-hover:bg-blue-600 group-hover:text-white transition-colors';

    if (btn.dataset.step === sidebarStep) {
      // Active state
      btn.className = 'w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium text-blue-700 bg-blue-50 flex items-center shadow-sm';
      if (icon) icon.className = 'w-6 h-6 mr-3 flex items-center justify-center rounded-md bg-blue-600 text-white';
    }
  });
}

// Logs Logic
async function loadLogs() {
    if (!logsContent) return;
    
    // Only show loading if empty to allow seamless refresh
    if (!logsContent.hasChildNodes()) {
        logsContent.innerHTML = '<div class="text-gray-500">加载中...</div>';
    }
    
    try {
        const level = logLevelFilter ? logLevelFilter.value : '';
        const pid = projectId || '';
        // Increase limit to 1000 to allow viewing earlier logs
        const url = `/api/logs?limit=1000&level=${level}&project_id=${pid}`;
        
        const res = await fetch(url);
        const data = await res.json();
        
        // Don't clear if we have data, just replace content to maintain scroll position if possible?
        // But logs usually append. For "history", we fetch all.
        // Simple approach: Replace all.
        logsContent.innerHTML = '';
        if (data.logs && data.logs.length > 0) {
            data.logs.forEach(log => {
                const div = document.createElement('div');
                div.className = 'font-mono text-xs border-b border-gray-800 pb-1 mb-1';
                
                let colorClass = 'text-gray-300';
                if (log.level === 'ERROR') colorClass = 'text-red-400 font-bold';
                if (log.level === 'WARN') colorClass = 'text-yellow-400';
                if (log.level === 'INFO') colorClass = 'text-blue-300';
                
                // Format details nicely
                let detailsHtml = '';
                if (log.details) {
                    try {
                        const jsonStr = JSON.stringify(log.details, null, 2);
                        detailsHtml = `<pre class="text-gray-500 mt-1 ml-4 text-[10px] overflow-x-auto bg-gray-900/50 p-1 rounded">${escapeHtml(jsonStr)}</pre>`;
                    } catch(e) {
                        detailsHtml = `<div class="text-gray-500 mt-1 ml-4 text-[10px]">${log.details}</div>`;
                    }
                }

                div.innerHTML = `
                    <div class="flex flex-wrap break-all">
                        <span class="text-gray-500 mr-2 shrink-0">[${new Date(log.timestamp).toLocaleTimeString()}]</span>
                        <span class="${colorClass} mr-2 shrink-0">[${log.level}]</span>
                        <span class="text-gray-400 mr-2 shrink-0">[${log.module || 'sys'}]</span>
                        <span class="text-white break-words">${escapeHtml(log.message)}</span>
                    </div>
                    ${detailsHtml}
                `;
                logsContent.appendChild(div);
            });
        } else {
            logsContent.innerHTML = '<div class="text-gray-500 italic">暂无日志</div>';
        }
    } catch (e) {
        logsContent.innerHTML = `<div class="text-red-500">加载失败: ${e.message}</div>`;
    }
}

// History Logic
async function loadHistory() {
  try {
    const params = new URLSearchParams();
    const searchVal = document.getElementById('historySearch')?.value;
    if (searchVal) params.append('name', searchVal);
    
    const status = document.getElementById('filterStatus')?.value;
    if (status) params.append('status', status);
    
    const platform = document.getElementById('filterPlatform')?.value;
    if (platform) params.append('platform', platform);
    
    const inputType = document.getElementById('filterInputType')?.value;
    if (inputType) params.append('input_type', inputType);
    
    const ratio = document.getElementById('filterRatio')?.value;
    if (ratio) params.append('aspect_ratio', ratio);
    
    const resolution = document.getElementById('filterResolution')?.value;
    if (resolution) params.append('resolution', resolution);
    
    const res = await fetch(`/api/projects?${params.toString()}`);
    const data = await res.json();
    historyList.innerHTML = '';
    
    const countEl = document.getElementById('projectCount');
    if (countEl) countEl.textContent = data.projects ? data.projects.length : 0;
    
    if (data.projects && data.projects.length > 0) {
      data.projects.forEach(p => {
        const div = document.createElement('div');
        div.className = 'px-3 py-2.5 rounded-lg hover:bg-gray-50 cursor-pointer text-sm text-gray-600 hover:text-gray-900 transition-all group border border-transparent hover:border-gray-100';
        
        // Show status indicator
        const statusColors = {
            'completed': 'bg-green-500',
            'processing': 'bg-blue-500',
            'failed': 'bg-red-500',
            'pending': 'bg-gray-400'
        };
        const dotColor = statusColors[p.status] || 'bg-gray-400';
        
        div.innerHTML = `
            <div class="flex items-center justify-between w-full">
                <div class="flex items-center truncate">
                    <span class="w-2 h-2 rounded-full ${dotColor} mr-2 flex-shrink-0"></span>
                    <span class="truncate" title="${p.project_name}">${p.project_name}</span>
                </div>
                <div class="text-[10px] text-gray-400 ml-2 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">${p.created_at ? new Date(p.created_at).toLocaleDateString() : ''}</div>
            </div>
        `;
        div.onclick = () => showProjectDetails(p.project_id);
        historyList.appendChild(div);
      });
    } else {
        historyList.innerHTML = '<div class="text-xs text-gray-400 text-center py-4">暂无项目</div>';
    }
  } catch (e) {
    console.error('Failed to load history', e);
    historyList.innerHTML = '<div class="text-xs text-red-400 text-center py-4">加载失败</div>';
  }
}

let currentDetailId = null;
async function showProjectDetails(id) {
    currentDetailId = id;
    projectDetailsModal.classList.remove('hidden');
    
    // Reset fields
    pdName.textContent = '加载中...';
    pdId.textContent = '';
    pdCreated.textContent = '';
    pdUpdated.textContent = '';
    pdStatus.textContent = '';
    pdPlatform.textContent = '';
    pdTokens.textContent = '-';
    pdVideoDuration.textContent = '-';
    pdShots.textContent = '-';
    pdImages.textContent = '-';
    pdVideos.textContent = '-';
    if(document.getElementById('pd_aspect_ratio')) document.getElementById('pd_aspect_ratio').textContent = '-';
    if(document.getElementById('pd_resolution')) document.getElementById('pd_resolution').textContent = '-';
    if(document.getElementById('pd_input_type')) document.getElementById('pd_input_type').textContent = '-';

    try {
        const res = await fetch(`/api/projects/${id}`);
        const p = await res.json();
        
        pdName.textContent = p.project_name;
        pdId.textContent = p.project_id;
        pdCreated.textContent = p.created_at ? new Date(p.created_at).toLocaleString() : '未知';
        pdUpdated.textContent = p.updated_at ? new Date(p.updated_at).toLocaleString() : '未知';
        pdStatus.textContent = p.status || 'Unknown';
        
        const platformKey = (p.topic_meta && p.topic_meta.platform) ? p.topic_meta.platform : 'volcengine';
        const platformMap = {
            'volcengine': 'Volcengine',
            'byteplus': 'BytePlus'
        };
        pdPlatform.textContent = platformMap[platformKey] || platformKey;

        pdCurrentStage.textContent = STEP_NAMES[p.current_step] || '未知';
        
        // Add new fields: Ratio, Resolution, Input Type
        if(document.getElementById('pd_aspect_ratio')) {
            document.getElementById('pd_aspect_ratio').textContent = (p.topic_meta && p.topic_meta.aspect_ratio) ? p.topic_meta.aspect_ratio : '16:9';
        }
        if(document.getElementById('pd_resolution')) {
            document.getElementById('pd_resolution').textContent = (p.topic_meta && p.topic_meta.resolution) ? p.topic_meta.resolution : '1080p';
        }
        if(document.getElementById('pd_input_type')) {
            const typeMap = {
                'topic': '基于主题',
                'script': '上传剧本'
            };
            document.getElementById('pd_input_type').textContent = typeMap[p.input_type] || p.input_type || '未知';
        }
        
        // Tokens
        if (p.total_tokens) {
            pdTokens.textContent = p.total_tokens.total_tokens || 0;
        } else {
            pdTokens.textContent = 0;
        }

        pdShots.textContent = p.storyboard?.shots?.length || 0;
        
        // Count images
        if (p.usage_stats && typeof p.usage_stats.total_images !== 'undefined') {
             pdImages.textContent = p.usage_stats.total_images;
        } else {
             let imgCount = 0;
             if (p.shot_images) {
                  Object.values(p.shot_images).forEach(list => imgCount += list.filter(x => !!x).length);
             } else if (p.image_paths) {
                  imgCount = p.image_paths.filter(path => !!path).length;
             }
             pdImages.textContent = imgCount;
        }
        
        // Count videos & duration (Cumulative)
        if (p.usage_stats && typeof p.usage_stats.total_videos !== 'undefined') {
             pdVideos.textContent = p.usage_stats.total_videos;
             pdVideoDuration.textContent = (p.usage_stats.total_video_duration || 0).toFixed(1) + ' 秒';
        } else {
             // Fallback to current if no cumulative
             pdVideos.textContent = p.video_paths?.length || 0;
             let totalDuration = 0;
             if (p.video_paths && p.storyboard?.shots) {
                  p.storyboard.shots.forEach((shot, i) => {
                      if (p.video_paths[i]) {
                          totalDuration += parseFloat(shot.duration || 0);
                      }
                  });
             }
             pdVideoDuration.textContent = totalDuration.toFixed(1) + ' 秒';
        }
        
        // Project Duration (Current)
        let projectDuration = 0;
        if (p.storyboard?.shots) {
            projectDuration = p.storyboard.shots.reduce((acc, shot) => acc + parseFloat(shot.duration || 0), 0);
        }
        pdProjectDuration.textContent = projectDuration.toFixed(1) + ' 秒';
        
    } catch(e) {
        console.error(e);
        pdName.textContent = '加载失败';
    }
}

async function deleteProject() {
    if (!currentDetailId) return;
    if (!confirm('确定要删除该项目吗？此操作无法撤销。')) return;

    try {
        const res = await fetch(`/api/projects/${currentDetailId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('删除失败');
        
        projectDetailsModal.classList.add('hidden');
        loadHistory();
        
        // If current loaded project is deleted, clear view or switch to input
        if (projectId === currentDetailId) {
            projectId = null;
            switchTab('input');
            updateStatus('项目已删除');
        }
    } catch (e) {
        alert(e.message);
    }
}

// Project Creation & Logic
async function createProject() {
  createBtn.disabled = true;
  createStatus.textContent = '创建中...';
  
  try {
    let body = {};
    if (mode === 'topic') {
      const topic = document.getElementById('topic').value.trim();
      if (!topic) throw new Error('请输入主题');
      body = {
        input_type: 'topic',
        input_content: topic,
        duration: parseInt(document.getElementById('duration').value || '3', 10),
        style: document.getElementById('style').value,
        visual_style: document.getElementById('visualStyle').value,
        audience: document.getElementById('audience').value,
        aspect_ratio: selectedRatio,
        resolution: selectedResolution
      };
    } else {
      const script = document.getElementById('scriptTextInput').value.trim();
      if (!script) throw new Error('请输入剧本');
      body = {
        input_type: 'script',
        input_content: script,
        style: document.getElementById('style').value, // Use the common style dropdown (though hidden, user might want defaults or we should expose it?)
        visual_style: document.getElementById('visualStyleScript').value,
        aspect_ratio: selectedRatio,
        resolution: selectedResolution
      };
    }

    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '创建失败');
    
    projectId = data.project_id;
    updateStatus(`项目已创建: ${data.project_id}`, 'green');
    loadHistory();
    
    // Switch to Script tab immediately
    switchTab('script');
    
    // If topic mode, start script generation automatically
    if (mode === 'topic') {
      await generateScript();
    } else {
      // Script mode, just load the script
      outScript.value = body.input_content;
    }

  } catch (e) {
    updateStatus('错误: ' + e.message, 'red');
    createStatus.textContent = '';
  } finally {
    createBtn.disabled = false;
  }
}

function updateNextButtonState(p) {
    if (!p) return;

    // Script -> Characters
    if (btnNextToCharacters) {
        btnNextToCharacters.disabled = !p.script;
        btnNextToCharacters.classList.toggle('opacity-50', !p.script);
    }

    // Characters -> Scenes
    const hasChars = p.characters && p.characters.length > 0;
    if (btnNextToScenes) {
        btnNextToScenes.disabled = !hasChars;
        btnNextToScenes.classList.toggle('opacity-50', !hasChars);
    }

    // Scenes -> Storyboard
    const hasScenes = p.scenes && p.scenes.length > 0;
    if (btnNextToStoryboard) {
        btnNextToStoryboard.disabled = !hasScenes;
        btnNextToStoryboard.classList.toggle('opacity-50', !hasScenes);
    }

    // Storyboard -> Prompts
    // Requirement: Storyboard has shots
    const hasShots = p.storyboard && p.storyboard.shots && p.storyboard.shots.length > 0;
    if (btnNextToPrompts) {
        btnNextToPrompts.disabled = !hasShots;
        btnNextToPrompts.classList.toggle('opacity-50', !hasShots);
        btnNextToPrompts.classList.toggle('cursor-not-allowed', !hasShots);
    }

    // Prompts -> Images
    // Requirement: Image prompts exist
    const hasPrompts = p.image_prompts && p.image_prompts.length > 0;
    if (btnNextToImages) {
        btnNextToImages.disabled = !hasPrompts;
        btnNextToImages.classList.toggle('opacity-50', !hasPrompts);
        btnNextToImages.classList.toggle('cursor-not-allowed', !hasPrompts);
    }

    // Images -> Videos
    // Requirement: All shots have at least one image
    let allShotsHaveImages = false;
    if (hasShots && p.shot_images) {
        // Check if every shot number (1..N) is present in shot_images and has at least 1 image
        const shotCount = p.storyboard.shots.length;
        allShotsHaveImages = true;
        for (let i = 1; i <= shotCount; i++) {
            if (!p.shot_images[i] || p.shot_images[i].length === 0) {
                allShotsHaveImages = false;
                break;
            }
        }
    } else if (hasShots && p.image_paths) {
        // Legacy fallback
        allShotsHaveImages = p.image_paths.length >= p.storyboard.shots.length && p.image_paths.every(path => !!path);
    }

    if (btnNextToVideos) {
        btnNextToVideos.disabled = !allShotsHaveImages;
        btnNextToVideos.classList.toggle('opacity-50', !allShotsHaveImages);
        btnNextToVideos.classList.toggle('cursor-not-allowed', !allShotsHaveImages);
    }

    // Videos -> Output (Merge)
    // Requirement: All shots have a video
    let allShotsHaveVideos = false;
    if (hasShots && p.video_paths) {
        // video_paths is a list corresponding to shots
        allShotsHaveVideos = p.video_paths.length >= p.storyboard.shots.length && p.video_paths.every(path => !!path);
    }

    if (btnMerge) {
        btnMerge.disabled = !allShotsHaveVideos;
        btnMerge.classList.toggle('opacity-50', !allShotsHaveVideos);
        btnMerge.classList.toggle('cursor-not-allowed', !allShotsHaveVideos);
    }
}

async function loadProject(id, shouldSwitchTab = true) {
  projectId = id;
  const res = await fetch(`/api/projects/${id}`);
  const p = await res.json();
  if (!res.ok) return;

  // Cache current project state
  currentProject = p;

  updateStatus(`当前项目: ${p.project_name} (${p.status})`);

  // Update Next Buttons State
  updateNextButtonState(p);

  // Populate Views
  if (p.script) outScript.value = p.script;
  else if (p.input_type === 'script') outScript.value = p.input_content;
  else outScript.value = '';

  renderStoryboard(p);
  renderCharacters(p);
  renderScenes(p);
  renderPrompts(p);
  renderImages(p);
  renderVideos(p);
  renderOutput(p);

  // Handle Loading States
  if (p.storyboard && p.storyboard.shots) setLoading('storyboard', false);
  if (p.characters && p.characters.length > 0) setLoading('characters', false);
  if (p.scenes && p.scenes.length > 0) setLoading('scenes', false);
  if (p.image_prompts && p.image_prompts.length > 0) setLoading('prompts', false);
  if (p.shot_images && Object.keys(p.shot_images).length > 0) setLoading('images', false);
  if (p.video_paths && p.video_paths.length > 0) setLoading('videos', false);
  
  // Special case: if status is completed, hide all
  if (p.status === 'completed') {
      ['storyboard', 'prompts', 'images', 'videos', 'characters', 'scenes'].forEach(s => setLoading(s, false));
      if (pollingInterval) {
          clearInterval(pollingInterval);
          pollingInterval = null;
          updateStatus('所有任务已完成', 'green');
          setInteractionState(true);
      }
  }

  if (shouldSwitchTab) {
      if (p.status === 'completed' || p.final_video) {
          switchTab('output');
      } else {
          // Auto-resume logic
          const targetTab = STEP_TABS[p.current_step] || 'script';
          switchTab(targetTab);
      }
  }
}

function setLoading(step, isLoading) {
    const el = {
        storyboard: storyboardLoading,
        prompts: promptsLoading,
        images: imagesLoading,
        videos: videosLoading,
        characters: charLoading,
        scenes: sceneLoading
    }[step];
    if (el) {
        if (isLoading) el.classList.remove('hidden');
        else el.classList.add('hidden');
    }
}

// Script Handling
async function generateScript() {
  scriptLoading.classList.remove('hidden');
  setInteractionState(false);
  try {
    const res = await fetch(`/api/projects/${projectId}/script`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '生成失败');
    
    if (data.task_id) {
        updateStatus(`剧本生成中... Task ID: ${data.task_id}`, 'blue');
        startPolling(data.task_id);
    } else if (data.script) {
        outScript.value = data.script;
        updateStatus('剧本生成完成', 'green');
        scriptLoading.classList.add('hidden');
        setInteractionState(true);
    }
  } catch (e) {
    updateStatus('剧本生成失败: ' + e.message, 'red');
    scriptLoading.classList.add('hidden');
    setInteractionState(true);
  }
}

function toggleScriptEdit() {
  isScriptEditing = !isScriptEditing;
  if (isScriptEditing) {
    outScript.readOnly = false;
    outScript.classList.add('border', 'border-blue-300', 'shadow-inner');
    btnEditScript.textContent = '取消编辑';
    btnEditScript.classList.add('bg-red-50', 'text-red-600', 'border-red-200');
    btnSaveScript.classList.remove('hidden');
  } else {
    outScript.readOnly = true;
    outScript.classList.remove('border', 'border-blue-300', 'shadow-inner');
    btnEditScript.textContent = '✏️ 编辑模式';
    btnEditScript.classList.remove('bg-red-50', 'text-red-600', 'border-red-200');
    btnSaveScript.classList.add('hidden');
  }
}

async function saveScriptContent() {
  const content = outScript.value;
  try {
    // Call the new Update API
    const res = await fetch(`/api/projects/${projectId}/script`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script: content }) 
    });
    
    if (!res.ok) throw new Error('保存失败');

    toggleScriptEdit();
    updateStatus('剧本已保存', 'green');
  } catch (e) {
    updateStatus('保存失败: ' + e.message, 'red');
  }
}

async function optimizeScript() {
  const feedback = prompt("请输入优化建议 (例如：增加更多对话，让节奏更紧凑):");
  if (!feedback) return;

  scriptLoading.classList.remove('hidden');
  try {
    const res = await fetch(`/api/projects/${projectId}/script/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        script: outScript.value,
        feedback: feedback 
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || '优化失败');
    
    outScript.value = data.script;
    updateStatus('剧本优化完成', 'green');
  } catch (e) {
    updateStatus('优化失败: ' + e.message, 'red');
  } finally {
    scriptLoading.classList.add('hidden');
  }
}

// Character Handling
function renderCharacters(p) {
  charList.innerHTML = '';
  const data = p.characters || [];

  if (data.length === 0) {
    charEmpty.classList.remove('hidden');
    // Hide subsequent buttons if no chars
    if(btnGenCharPrompts) btnGenCharPrompts.classList.add('opacity-50', 'cursor-not-allowed');
    if(btnGenCharImages) btnGenCharImages.classList.add('opacity-50', 'cursor-not-allowed');
    return;
  }

  charEmpty.classList.add('hidden');
  if(btnGenCharPrompts) btnGenCharPrompts.classList.remove('opacity-50', 'cursor-not-allowed');
  // Only enable image gen if prompts exist (simple check: if first char has prompt)
  if(data[0].prompt) {
      if(btnGenCharImages) btnGenCharImages.classList.remove('opacity-50', 'cursor-not-allowed');
  } else {
      if(btnGenCharImages) btnGenCharImages.classList.add('opacity-50', 'cursor-not-allowed');
  }

  data.forEach((char, index) => {
    const div = document.createElement('div');
    div.className = 'bg-white p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-all flex flex-col md:flex-row gap-6';
    
    // Image placeholder or actual image
    let imgHtml = '';
    if (char.image_path) {
        const normalizedSrc = normalizePath(char.image_path);
        const sep = normalizedSrc.includes('?') ? '&' : '?';
        const displaySrc = `${normalizedSrc}${sep}t=${Date.now()}`;
        
        imgHtml = `
         <div class="relative group w-full md:w-1/3 aspect-[3/4] rounded-lg overflow-hidden cursor-zoom-in" onclick="zoomImage('${normalizedSrc}')">
            <img src="${displaySrc}" class="w-full h-full object-cover hover:scale-105 transition-transform" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNjY2MiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cmVjdCB4PSIzIiB5PSIzIiB3aWR0aD0iMTgiIGhlaWdodD0iMTgiIHJ4PSIyIiByeT0iMiIvPjxjaXJjbGUgY3g9IjguNSIgY3k9IjguNSIgcj0iMS41Ii8+PHBvbHlsaW5lIHBvaW50cz0iMjEgMTUgMTYgMTAgNSAyMSIvPjwvc3ZnPg=='">
            <div class="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <button onclick="event.stopPropagation(); regenerateCharacterImage(${index})" class="bg-white/90 text-blue-600 px-3 py-1.5 rounded-lg text-xs font-bold shadow hover:bg-white transition-colors">
                    🔄 重新生成照片
                </button>
            </div>
         </div>`;
    } else {
        imgHtml = `
         <div class="relative group w-full md:w-1/3 aspect-[3/4] bg-gray-100 rounded-lg flex items-center justify-center text-gray-400">
            <span class="text-4xl">👤</span>
            <div class="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <button onclick="event.stopPropagation(); regenerateCharacterImage(${index})" class="bg-white/90 text-blue-600 px-3 py-1.5 rounded-lg text-xs font-bold shadow hover:bg-white transition-colors">
                    🔄 生成照片
                </button>
            </div>
         </div>`;
    }

    div.innerHTML = `
      ${imgHtml}
      <div class="flex-1 space-y-3">
        <div class="flex justify-between items-start">
            <h3 class="text-xl font-bold text-slate-800 flex items-center gap-2">
                <input id="charName_${index}" class="bg-transparent border-b border-transparent hover:border-gray-300 focus:border-blue-500 outline-none w-32" value="${char.name || '未命名'}">
            </h3>
            <div class="flex items-center gap-2">
                <input id="charGender_${index}" class="text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded-full border-none outline-none w-16 text-center" value="${char.gender || '未知'}">
                <span class="text-gray-300">/</span>
                <input id="charAge_${index}" class="text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded-full border-none outline-none w-16 text-center" value="${char.age || '未知'}">
                <button onclick="saveCharacterTraits(${index})" class="text-xs bg-green-50 text-green-600 px-2 py-1 rounded hover:bg-green-100 transition-colors ml-2">保存设定</button>
            </div>
        </div>
        
        <div class="grid grid-cols-2 gap-4 text-sm">
            <div>
                <label class="block text-xs font-bold text-gray-400 uppercase">性格</label>
                <textarea id="charPersonality_${index}" class="w-full bg-transparent border-b border-dashed border-gray-200 focus:border-blue-500 outline-none resize-none text-gray-700 h-16">${char.personality || '-'}</textarea>
            </div>
            <div>
                <label class="block text-xs font-bold text-gray-400 uppercase">服装</label>
                <textarea id="charClothing_${index}" class="w-full bg-transparent border-b border-dashed border-gray-200 focus:border-blue-500 outline-none resize-none text-gray-700 h-16">${char.clothing || '-'}</textarea>
            </div>
        </div>
        
        <div>
            <label class="block text-xs font-bold text-gray-400 uppercase mb-1">外貌特征</label>
            <textarea id="charAppearance_${index}" class="w-full bg-gray-50 border border-gray-200 rounded p-2 text-sm text-gray-700 resize-none outline-none focus:border-blue-500 h-16">${char.appearance || '-'}</textarea>
        </div>

        <div>
            <div class="flex items-center justify-between mb-1">
                <label class="block text-xs font-bold text-gray-400 uppercase">生图提示词</label>
                <div class="space-x-2">
                    <button onclick="saveCharacterPrompt(${index})" class="text-xs text-blue-600 hover:text-blue-800 font-medium">保存</button>
                    <button onclick="regenerateCharacterPrompt(${index})" class="text-xs text-blue-600 hover:text-blue-800 font-medium">重新生成</button>
                </div>
            </div>
            <textarea id="charPrompt_${index}" class="w-full bg-gray-50 border border-gray-200 rounded p-2 text-xs text-gray-600 h-20 resize-none outline-none focus:border-blue-500">${char.prompt || ''}</textarea>
        </div>
      </div>
    `;
    charList.appendChild(div);
  });
}

window.saveCharacterPrompt = async function(index) {
    const promptVal = document.getElementById(`charPrompt_${index}`).value;
    updateStatus(`正在保存角色提示词...`, 'blue');
    
    try {
        const res = await fetch(`/api/projects/${projectId}/characters/${index}/prompt`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptVal })
        });
        
        if (!res.ok) throw new Error('保存失败');
        
        // Update local state to prevent UI revert on re-render
        if (currentProject && currentProject.characters && currentProject.characters[index]) {
            currentProject.characters[index].prompt = promptVal;
        }

        updateStatus('角色提示词已保存', 'green');
    } catch (e) {
        updateStatus(`保存失败: ${e.message}`, 'red');
    }
};

window.regenerateCharacterPrompt = async function(index) {
    updateStatus(`正在重新生成角色提示词...`, 'blue');
    // Show a loading state on the textarea or button? 
    // For now global status is fine, maybe disable textarea
    const textarea = document.getElementById(`charPrompt_${index}`);
    textarea.disabled = true;
    
    try {
        const res = await fetch(`/api/projects/${projectId}/characters/${index}/prompt/regenerate`, {
            method: 'POST'
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '生成失败');
        
        textarea.value = data.character.prompt;
        updateStatus('角色提示词生成完成', 'green');
    } catch (e) {
        updateStatus(`生成失败: ${e.message}`, 'red');
    } finally {
        textarea.disabled = false;
    }
};

window.saveCharacterTraits = async function(index) {
    const name = document.getElementById(`charName_${index}`).value;
    const gender = document.getElementById(`charGender_${index}`).value;
    const age = document.getElementById(`charAge_${index}`).value;
    const personality = document.getElementById(`charPersonality_${index}`).value;
    const clothing = document.getElementById(`charClothing_${index}`).value;
    const appearance = document.getElementById(`charAppearance_${index}`).value;
    
    updateStatus(`正在保存角色设定...`, 'blue');
    
    try {
        const res = await fetch(`/api/projects/${projectId}/characters/${index}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name, gender, age, personality, clothing, appearance
            })
        });
        
        if (!res.ok) throw new Error('保存失败');
        
        // Update local state
        if (currentProject && currentProject.characters && currentProject.characters[index]) {
            Object.assign(currentProject.characters[index], {
                name, gender, age, personality, clothing, appearance
            });
        }
        
        // No need to reload whole project, just status
        updateStatus('角色设定已保存', 'green');
    } catch (e) {
        updateStatus(`保存失败: ${e.message}`, 'red');
    }
};

window.regenerateCharacterImage = async function(index) {
    updateStatus(`正在生成角色照片...`, 'blue');
    setInteractionState(false);
    
    // Get latest prompt from UI
    const promptVal = document.getElementById(`charPrompt_${index}`).value;

    // Update local state
    if (currentProject && currentProject.characters && currentProject.characters[index]) {
        currentProject.characters[index].prompt = promptVal;
    }

    try {
        const res = await fetch(`/api/projects/${projectId}/characters/${index}/image/regenerate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptVal })
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '生成失败');
        
        if (data.task_id) {
            updateStatus(`角色生成中... Task ID: ${data.task_id}`, 'blue');
            startPolling(data.task_id);
        } else {
            await loadProject(projectId, false);
            updateStatus('角色照片生成完成', 'green');
            setInteractionState(true);
        }
    } catch (e) {
        updateStatus(`生成失败: ${e.message}`, 'red');
        setInteractionState(true);
    }
};

// Scene Handling
function renderScenes(p) {
  sceneList.innerHTML = '';
  const data = p.scenes || [];

  if (data.length === 0) {
    sceneEmpty.classList.remove('hidden');
    if(btnGenScenePrompts) btnGenScenePrompts.classList.add('opacity-50', 'cursor-not-allowed');
    if(btnGenSceneImages) btnGenSceneImages.classList.add('opacity-50', 'cursor-not-allowed');
    return;
  }

  sceneEmpty.classList.add('hidden');
  if(btnGenScenePrompts) btnGenScenePrompts.classList.remove('opacity-50', 'cursor-not-allowed');
  if(data[0].prompt) {
      if(btnGenSceneImages) btnGenSceneImages.classList.remove('opacity-50', 'cursor-not-allowed');
  } else {
      if(btnGenSceneImages) btnGenSceneImages.classList.add('opacity-50', 'cursor-not-allowed');
  }

  data.forEach((scene, index) => {
    const div = document.createElement('div');
    div.className = 'bg-white p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-all flex flex-col md:flex-row gap-6';
    
    let imgHtml = '';
    if (processingScenes.has(index)) {
        imgHtml = `
         <div class="relative w-full md:w-1/3 aspect-video bg-gray-100 rounded-lg flex items-center justify-center text-gray-400">
             <div class="flex flex-col items-center">
                 <div class="w-8 h-8 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-2"></div>
                 <span class="text-xs">生成中...</span>
             </div>
         </div>`;
    } else if (scene.image_path) {
        imgHtml = `
         <div class="relative group w-full md:w-1/3 aspect-video rounded-lg overflow-hidden cursor-zoom-in" onclick="zoomImage('${normalizePath(scene.image_path)}')">
            <img src="${normalizePath(scene.image_path)}" class="w-full h-full object-cover hover:scale-105 transition-transform">
            <div class="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <button onclick="event.stopPropagation(); regenerateSceneImage(${index})" class="bg-white/90 text-blue-600 px-3 py-1.5 rounded-lg text-xs font-bold shadow hover:bg-white transition-colors">
                    🔄 重新生成场景图
                </button>
            </div>
         </div>`;
    } else {
        imgHtml = `
         <div class="relative group w-full md:w-1/3 aspect-video bg-gray-100 rounded-lg flex items-center justify-center text-gray-400">
            <span class="text-4xl">🏞️</span>
            <div class="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <button onclick="event.stopPropagation(); regenerateSceneImage(${index})" class="bg-white/90 text-blue-600 px-3 py-1.5 rounded-lg text-xs font-bold shadow hover:bg-white transition-colors">
                    🔄 生成场景图
                </button>
            </div>
         </div>`;
    }

    div.innerHTML = `
      ${imgHtml}
      <div class="flex-1 space-y-3">
        <div class="flex justify-between items-start">
            <h3 class="text-xl font-bold text-slate-800 flex items-center gap-2">
                <input id="sceneName_${index}" class="bg-transparent border-b border-transparent hover:border-gray-300 focus:border-blue-500 outline-none w-48" value="${scene.name || '未命名'}">
            </h3>
            <div class="flex items-center gap-2">
                 <input id="sceneTime_${index}" class="text-xs bg-green-50 text-green-600 px-2 py-1 rounded-full border-none outline-none w-20 text-center" value="${scene.time || '未知'}">
                 <span class="text-gray-300">/</span>
                 <input id="sceneLocation_${index}" class="text-xs bg-green-50 text-green-600 px-2 py-1 rounded-full border-none outline-none w-20 text-center" value="${scene.location || '未知'}">
                 <button onclick="saveSceneDescription(${index})" class="text-xs bg-blue-50 text-blue-600 px-2 py-1 rounded hover:bg-blue-100 transition-colors ml-2">保存描述</button>
            </div>
        </div>
        
        <div class="grid grid-cols-2 gap-4 text-sm">
            <div>
                <label class="block text-xs font-bold text-gray-400 uppercase">氛围</label>
                <textarea id="sceneAtmosphere_${index}" class="w-full bg-transparent border-b border-dashed border-gray-200 focus:border-blue-500 outline-none resize-none text-gray-700 h-16">${scene.atmosphere || '-'}</textarea>
            </div>
            <div>
                <label class="block text-xs font-bold text-gray-400 uppercase">关键元素</label>
                <textarea id="sceneElements_${index}" class="w-full bg-transparent border-b border-dashed border-gray-200 focus:border-blue-500 outline-none resize-none text-gray-700 h-16">${scene.elements || '-'}</textarea>
            </div>
        </div>

        <div>
            <div class="flex items-center justify-between mb-1">
                <label class="block text-xs font-bold text-gray-400 uppercase">生图提示词</label>
                <div class="space-x-2">
                    <button onclick="saveScenePrompt(${index})" class="text-xs text-blue-600 hover:text-blue-800 font-medium">保存</button>
                    <button onclick="regenerateScenePrompt(${index})" class="text-xs text-blue-600 hover:text-blue-800 font-medium">重新生成</button>
                </div>
            </div>
            <textarea id="scenePrompt_${index}" class="w-full bg-gray-50 border border-gray-200 rounded p-2 text-xs text-gray-600 h-20 resize-none outline-none focus:border-blue-500">${scene.prompt || ''}</textarea>
        </div>
      </div>
    `;
    sceneList.appendChild(div);
  });
}

window.saveSceneDescription = async function(index) {
    const name = document.getElementById(`sceneName_${index}`).value;
    const time = document.getElementById(`sceneTime_${index}`).value;
    const location = document.getElementById(`sceneLocation_${index}`).value;
    const atmosphere = document.getElementById(`sceneAtmosphere_${index}`).value;
    const elements = document.getElementById(`sceneElements_${index}`).value;
    
    updateStatus(`正在保存场景描述...`, 'blue');
    
    try {
        const res = await fetch(`/api/projects/${projectId}/scenes/${index}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name, time, location, atmosphere, elements
            })
        });
        
        if (!res.ok) throw new Error('保存失败');
        
        updateStatus('场景描述已保存', 'green');
    } catch (e) {
        updateStatus(`保存失败: ${e.message}`, 'red');
    }
};

window.saveScenePrompt = async function(index) {
    const promptVal = document.getElementById(`scenePrompt_${index}`).value;
    updateStatus(`正在保存场景提示词...`, 'blue');
    
    try {
        const res = await fetch(`/api/projects/${projectId}/scenes/${index}/prompt`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptVal })
        });
        
        if (!res.ok) throw new Error('保存失败');
        
        // Update local state to prevent UI revert on re-render
        if (currentProject && currentProject.scenes && currentProject.scenes[index]) {
            currentProject.scenes[index].prompt = promptVal;
        }

        updateStatus('场景提示词已保存', 'green');
    } catch (e) {
        updateStatus(`保存失败: ${e.message}`, 'red');
    }
};

window.regenerateScenePrompt = async function(index) {
    updateStatus(`正在重新生成场景提示词...`, 'blue');
    const textarea = document.getElementById(`scenePrompt_${index}`).value;
    const textareaEl = document.getElementById(`scenePrompt_${index}`);
    textareaEl.disabled = true;
    
    try {
        const res = await fetch(`/api/projects/${projectId}/scenes/${index}/prompt/regenerate`, {
            method: 'POST'
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '生成失败');
        
        textareaEl.value = data.scene.prompt;
        
        // Update local state
        if (currentProject && currentProject.scenes && currentProject.scenes[index]) {
            currentProject.scenes[index].prompt = data.scene.prompt;
        }
        
        updateStatus('场景提示词生成完成', 'green');
    } catch (e) {
        updateStatus(`生成失败: ${e.message}`, 'red');
    } finally {
        textareaEl.disabled = false;
    }
};

window.regenerateSceneImage = async function(index) {
    updateStatus(`正在生成场景图...`, 'blue');
    setInteractionState(false);
    
    // Get latest prompt from UI
    const promptVal = document.getElementById(`scenePrompt_${index}`).value;
    
    // Update local state immediately
    if (currentProject && currentProject.scenes && currentProject.scenes[index]) {
        currentProject.scenes[index].prompt = promptVal;
    }
    
    // Add to processing set and re-render to show spinner
    processingScenes.add(index);
    if (currentProject) renderScenes(currentProject);
    
    try {
        const res = await fetch(`/api/projects/${projectId}/scenes/${index}/image/regenerate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptVal })
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '生成失败');
        
        if (data.task_id) {
            updateStatus(`场景生成中... Task ID: ${data.task_id}`, 'blue');
            startPolling(data.task_id, () => {
                // On complete callback
                processingScenes.delete(index);
                // renderScenes will be called by loadProject inside startPolling
            });
        } else {
            await loadProject(projectId, false);
            updateStatus('场景图生成完成', 'green');
            setInteractionState(true);
            processingScenes.delete(index);
            if (currentProject) renderScenes(currentProject);
        }
    } catch (e) {
        updateStatus(`生成失败: ${e.message}`, 'red');
        setInteractionState(true);
        processingScenes.delete(index);
        if (currentProject) renderScenes(currentProject);
    }
};

// Storyboard Handling
function renderStoryboard(p) {
  storyboardList.innerHTML = '';
  const data = p.storyboard;

  if (!data || !data.shots || data.shots.length === 0) {
    storyboardEmpty.classList.remove('hidden');
    btnSaveStoryboard.classList.add('hidden');
    return;
  }

  storyboardEmpty.classList.add('hidden');
  btnSaveStoryboard.classList.remove('hidden');

  data.shots.forEach((shot, index) => {
    const div = document.createElement('div');
    div.className = 'bg-white p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-all';
    div.dataset.index = index;
    
    div.innerHTML = `
      <div class="flex items-center justify-between mb-4 border-b border-gray-100 pb-3">
        <div class="font-bold text-lg text-slate-800 flex items-center">
          <span class="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm mr-3">#${shot.shot_number}</span>
          镜头 ${shot.shot_number}
        </div>
        <div class="text-sm text-gray-500 bg-gray-50 px-3 py-1 rounded-full border border-gray-100">
          时长: <input class="w-12 bg-transparent border-b border-dashed border-gray-300 focus:border-blue-500 outline-none text-center" value="${shot.duration || 3}"> 秒
        </div>
      </div>
      
      <div class="grid grid-cols-2 gap-6">
        <div class="space-y-3">
           <div>
             <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">画面描述</label>
             <textarea class="sb-desc w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:border-blue-500 outline-none h-24 resize-none">${shot.description || ''}</textarea>
           </div>
           <div>
             <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">景别 & 运镜</label>
             <div class="grid grid-cols-2 gap-2">
               <input class="sb-type w-full bg-gray-50 border border-gray-200 rounded-lg p-2 text-sm focus:border-blue-500 outline-none" value="${shot.shot_type || ''}" placeholder="景别">
               <input class="sb-cam w-full bg-gray-50 border border-gray-200 rounded-lg p-2 text-sm focus:border-blue-500 outline-none" value="${shot.camera_movement || ''}" placeholder="运镜">
             </div>
           </div>
        </div>
        
        <div class="space-y-3">
           <div>
             <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">旁白 / 对话</label>
             <textarea class="sb-dialogue w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:border-blue-500 outline-none h-24 resize-none">${shot.dialogue || ''}</textarea>
           </div>
           <div>
             <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">角色动作</label>
             <input class="sb-action w-full bg-gray-50 border border-gray-200 rounded-lg p-2 text-sm focus:border-blue-500 outline-none" value="${shot.action || ''}">
           </div>
           <div>
             <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">角色 & 场景</label>
             <div class="grid grid-cols-2 gap-2">
               <input class="sb-char w-full bg-gray-50 border border-gray-200 rounded-lg p-2 text-sm focus:border-blue-500 outline-none" value="${shot.character || ''}" placeholder="角色">
               <input class="sb-scene w-full bg-gray-50 border border-gray-200 rounded-lg p-2 text-sm focus:border-blue-500 outline-none" value="${shot.scene || ''}" placeholder="场景">
             </div>
           </div>
        </div>
      </div>
    `;
    storyboardList.appendChild(div);
  });
}

async function saveStoryboard() {
  const shots = [];
  const cards = storyboardList.querySelectorAll(':scope > div');
  
  cards.forEach(card => {
    const index = parseInt(card.dataset.index);
    const duration = parseFloat(card.querySelector('input[value]').value); // Hacky selector, better use classes
    // Actually let's select by structure or class
    const durationInput = card.querySelector('.text-sm input'); 
    
    shots.push({
      shot_number: index + 1,
      duration: parseFloat(durationInput.value) || 3,
      description: card.querySelector('.sb-desc').value,
      shot_type: card.querySelector('.sb-type').value,
      camera_movement: card.querySelector('.sb-cam').value,
      dialogue: card.querySelector('.sb-dialogue').value,
      action: card.querySelector('.sb-action').value,
      character: card.querySelector('.sb-char').value,
      scene: card.querySelector('.sb-scene').value,
      // Preserve other fields if any? Ideally we merge, but here we rebuild.
      // Assuming 'mood' is lost if not editable? Let's add mood if needed. 
      // For MVP, just saving these is fine.
    });
  });

  const newStoryboard = {
    title: "Updated Storyboard", // We don't track title in UI yet
    shots: shots,
    total_shots: shots.length
  };

  try {
    const res = await fetch(`/api/projects/${projectId}/storyboard`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ storyboard: newStoryboard })
    });
    
    if (!res.ok) throw new Error('保存失败');
    updateStatus('分镜已保存', 'green');
  } catch (e) {
    updateStatus('保存分镜失败: ' + e.message, 'red');
  }
}


// Generic Step Execution
async function callStep(stepName, payload = {}) {
  if (!projectId) { alert('请先创建项目'); return; }
  
  const tabMap = { 
      merge: 'output',
      'characters/prompts': 'characters',
      'characters/images': 'characters',
      'scenes/prompts': 'scenes',
      'scenes/images': 'scenes'
  };
  switchTab(tabMap[stepName] || stepName);

  updateStatus(`正在执行: ${stepName}...`, 'blue');
  
  // Enable loading state
  // Only use global loading for steps that don't have partial/progressive rendering in the UI yet.
  if (stepName !== 'images' && stepName !== 'videos' && stepName !== 'characters/images' && stepName !== 'scenes/images') {
      setLoading(stepName.split('/')[0], true);
  }
  
  // Show merging progress UI specifically for merge
  if (stepName === 'merge') {
      finalVideoEl.innerHTML = `
          <div class="text-center w-full py-20">
             <div class="mb-6">
                <div class="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
                <div class="text-xl font-bold text-slate-800">正在拼接成片...</div>
                <div class="text-gray-500 mt-2">请稍候，这可能需要几分钟</div>
             </div>
          </div>
      `;
  }
  
  setInteractionState(false);

  // Optimistic UI Update: Set status to processing immediately for visual feedback
  if (currentProject) {
      currentProject.status = 'in_progress';
      
      if (stepName === 'images' && currentProject.storyboard?.shots) {
          currentProject.storyboard.shots.forEach(s => {
              currentProject[`shot_status_image_${s.shot_number}`] = 'processing';
          });
          renderImages(currentProject);
      } else if (stepName === 'videos' && currentProject.storyboard?.shots) {
           currentProject.storyboard.shots.forEach(s => {
              currentProject[`shot_status_video_${s.shot_number}`] = 'processing';
          });
          renderVideos(currentProject);
      }
  }

  try {
    const res = await fetch(`/api/projects/${projectId}/${stepName}`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    
    if (!res.ok) {
      if (data.message === 'skipped') {
        alert('已跳过此步骤');
      } else {
        throw new Error(data.error || '执行失败');
      }
    }
    
    if (data.task_id) {
        // Start polling
        updateStatus(`任务运行中: ${data.task_id}`, 'blue');
        startPolling(data.task_id);
    } else {
        await loadProject(projectId);
        updateStatus('执行成功', 'green');
        setInteractionState(true);
    }
    
    // Stay on correct tab
    switchTab(tabMap[stepName] || stepName);

  } catch (e) {
    updateStatus('错误: ' + e.message, 'red');
    setInteractionState(true);
    if (stepName !== 'images' && stepName !== 'videos' && stepName !== 'characters/images' && stepName !== 'scenes/images') {
        setLoading(stepName.split('/')[0], false);
    }
    // Revert UI on error
    if (stepName === 'merge') {
        renderOutput(currentProject); 
    }
    // Revert optimistic update on error by reloading
    if (projectId) loadProject(projectId, false);
  }
}

async function checkShotStatus() {
    // Just reload the project to get latest status
    if (projectId) {
        updateStatus('刷新状态中...', 'blue');
        await loadProject(projectId, false);
        updateStatus('状态已更新', 'green');
    }
}

let pollingInterval = null;
function startPolling(taskId, onComplete) {
    if (pollingInterval) clearInterval(pollingInterval);
    
    pollingInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/tasks/${taskId}`);
            if (!res.ok) return;
            const task = await res.json();
            
            if (task.status === 'completed') {
                clearInterval(pollingInterval);
                pollingInterval = null;
                updateStatus('任务已完成，正在同步数据...', 'green');
                
                // Add a small delay to ensure backend consistency
                await new Promise(r => setTimeout(r, 1500));
                
                // Call callback before loadProject if needed, or after?
                // If we want to clear processing flags before re-render, do it here.
                if (onComplete) onComplete();

                await loadProject(projectId, false); // Refresh data
                setInteractionState(true);
                
                // Hide loading indicators
                if (typeof scriptLoading !== 'undefined') scriptLoading.classList.add('hidden');
                ['storyboard', 'prompts', 'images', 'videos', 'characters', 'scenes'].forEach(s => setLoading(s, false));

            } else if (task.status === 'failed') {
                clearInterval(pollingInterval);
                pollingInterval = null;
                updateStatus('任务失败: ' + (task.error || '未知错误'), 'red');
                
                if (onComplete) onComplete();

                setInteractionState(true);
                if (typeof scriptLoading !== 'undefined') scriptLoading.classList.add('hidden');
                ['storyboard', 'prompts', 'images', 'videos', 'characters', 'scenes'].forEach(s => setLoading(s, false));
                await loadProject(projectId, false);
            } else {
                // Running
                updateStatus(`任务执行中... (${task.progress || 0}%)`, 'blue');
                // Refresh project data to show real-time progress (e.g. generated images)
                if (projectId) {
                    await loadProject(projectId, false);
                }
            }
        } catch(e) {
            console.error("Polling error", e);
        }
    }, 2000);
}

function updateStatus(msg, color='gray') {
  statusEl.textContent = msg;
  statusDot.className = `w-2 h-2 rounded-full mr-2 bg-${color}-500`;
}

// Render Functions
function renderPrompts(p) {
  promptsList.innerHTML = '';
  const imgPrompts = p.image_prompts || [];
  const vidPrompts = p.video_prompts || [];
  
  if (imgPrompts.length === 0) {
    promptsList.innerHTML = '<div class="text-gray-400 text-center py-10">点击上方按钮生成提示词</div>';
    if (btnSavePrompts) btnSavePrompts.classList.add('hidden');
    return;
  }

  if (btnSavePrompts) btnSavePrompts.classList.remove('hidden');

  imgPrompts.forEach((ip, i) => {
    const vp = vidPrompts[i] || {};
    const div = document.createElement('div');
    div.className = 'bg-white p-6 rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-all';
    div.dataset.index = i; // Store index for saving
    
    div.innerHTML = `
      <div class="font-bold mb-3 text-blue-600 flex items-center">
        <span class="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs mr-2">${ip.shot_number || (i+1)}</span>
        镜头 #${ip.shot_number || (i+1)}
      </div>
      <div class="grid grid-cols-2 gap-6">
        <div class="bg-gray-50 p-4 rounded-lg">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-gray-500 uppercase tracking-wider">图像提示词</span>
            <button onclick="regenerateSinglePrompt(${ip.shot_number || (i+1)}, 'image')" class="text-xs px-2 py-1 rounded bg-white border border-blue-200 text-blue-600 hover:bg-blue-50 transition-colors flex items-center">
              <span class="mr-1">🔄</span> 重新生成
            </button>
          </div>
          <textarea id="p_img_${i}" class="prompt-img w-full bg-transparent border border-gray-200 rounded p-2 text-sm text-gray-700 leading-relaxed focus:border-blue-500 outline-none resize-y h-32">${ip.positive_prompt || ''}</textarea>
        </div>
        <div class="bg-gray-50 p-4 rounded-lg">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-bold text-gray-500 uppercase tracking-wider">视频提示词</span>
            <button onclick="regenerateSinglePrompt(${ip.shot_number || (i+1)}, 'video')" class="text-xs px-2 py-1 rounded bg-white border border-blue-200 text-blue-600 hover:bg-blue-50 transition-colors flex items-center">
              <span class="mr-1">🔄</span> 重新生成
            </button>
          </div>
          <textarea id="p_vid_${i}" class="prompt-vid w-full bg-transparent border border-gray-200 rounded p-2 text-sm text-gray-700 leading-relaxed focus:border-blue-500 outline-none resize-y h-32">${vp.video_prompt || ''}</textarea>
        </div>
      </div>
    `;
    promptsList.appendChild(div);
  });
}

async function regenerateSinglePrompt(shotNumber, type) {
    updateStatus(`正在重新生成镜头 ${shotNumber} 的${type === 'image' ? '图像' : '视频'}提示词...`, 'blue');
    setInteractionState(false);
    
    try {
        const res = await fetch(`/api/projects/${projectId}/prompts/${shotNumber}/regenerate`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: type })
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || '生成失败');
        
        // Update UI locally without full reload to preserve scroll/focus if possible
        // Find the textarea
        // Note: renderPrompts uses index, but here we have shotNumber. 
        // Assuming shotNumber matches index+1 for now, or we search DOM.
        // Better to reload project data to be safe and consistent.
        
        await loadProject(projectId, false);
        updateStatus(`镜头 ${shotNumber} 提示词生成完成`, 'green');
        
    } catch (e) {
        updateStatus(`生成失败: ${e.message}`, 'red');
    } finally {
        setInteractionState(true);
    }
}

async function savePromptsData() {
  const cards = promptsList.querySelectorAll(':scope > div');
  const imgPrompts = [];
  const vidPrompts = [];

  // We need to reconstruct the arrays. 
  // Ideally we should merge with existing data to keep other fields like 'shot_number', 'style' etc.
  // But for now we rely on the index.
  // A better way is to fetch current project, update, then save.
  // Let's fetch first to be safe about other fields.
  
  try {
      const res = await fetch(`/api/projects/${projectId}`);
      const p = await res.json();
      if (!res.ok) throw new Error('获取项目信息失败');

      const existingImg = p.image_prompts || [];
      const existingVid = p.video_prompts || [];

      cards.forEach(card => {
        const index = parseInt(card.dataset.index);
        const imgVal = card.querySelector('.prompt-img').value;
        const vidVal = card.querySelector('.prompt-vid').value;

        // Update Image Prompt
        if (existingImg[index]) {
            existingImg[index].positive_prompt = imgVal;
        } else {
            // Fallback if index mismatch (shouldn't happen if no concurrent edits)
            existingImg[index] = { shot_number: index + 1, positive_prompt: imgVal };
        }

        // Update Video Prompt
        if (existingVid[index]) {
            existingVid[index].video_prompt = vidVal;
        } else {
            existingVid[index] = { shot_number: index + 1, video_prompt: vidVal };
        }
      });

      // Send update
      const updateRes = await fetch(`/api/projects/${projectId}/prompts`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
              image_prompts: existingImg,
              video_prompts: existingVid
          })
      });
      
      if (!updateRes.ok) throw new Error('保存失败');
      updateStatus('提示词已保存', 'green');

  } catch (e) {
      updateStatus('保存提示词失败: ' + e.message, 'red');
  }
}

function renderImages(p) {
  imagesEl.innerHTML = '';
  // Ensure we have a working dictionary
  const shotImages = p.shot_images ? JSON.parse(JSON.stringify(p.shot_images)) : {};
  
  // Sync from image_paths (legacy/current status source) to ensure we have at least the selected image
  if (p.image_paths) {
     p.image_paths.forEach((path, i) => {
         const shotNum = i + 1;
         if (path) {
             if (!shotImages[shotNum]) {
                 shotImages[shotNum] = [];
             }
             // Add if not present (simple check)
             if (!shotImages[shotNum].includes(path)) {
                 shotImages[shotNum].push(path);
             }
         }
     });
  }

  const shotsCount = p.storyboard?.shots?.length || 0;
  if (shotsCount === 0) {
      imagesEl.innerHTML = '<div class="text-gray-400 text-center py-10">请先生成分镜</div>';
      return;
  }

  // If we are generating (processing) or have images, render the list. 
  // If no images and not processing, show "Click to generate".
  const isGlobalProcessing = p.status === 'in_progress' || (currentProject && currentProject.status === 'in_progress');
  if (Object.keys(shotImages).length === 0 && !isGlobalProcessing && !p.image_prompts) {
    imagesEl.innerHTML = '<div class="text-gray-400 text-center py-10">点击上方按钮生成首图</div>';
    return;
  }
  
  for (let i = 1; i <= shotsCount; i++) {
    const images = shotImages[i] || [];
    
    // Get prompt
    const imgPrompts = p.image_prompts || [];
    const currentPrompt = imgPrompts.find(pr => pr.shot_number === i) || imgPrompts[i-1] || {};
    const promptText = currentPrompt.positive_prompt || '';

    // Check status
    const statusKey = `shot_status_image_${i}`;
    const statusVal = p.topic_meta ? p.topic_meta[statusKey] : (p[statusKey] || 'pending'); // Check both locations
    let statusBadge = '';
    let isShotProcessing = false;

    if (statusVal === 'processing') {
         statusBadge = '<span class="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-full animate-pulse">生成中...</span>';
         isShotProcessing = true;
    } else if (statusVal === 'failed') {
         statusBadge = '<span class="text-xs px-2 py-1 bg-red-100 text-red-700 rounded-full">生成失败</span>';
    } else if (statusVal === 'completed' || (images.length > 0)) {
         statusBadge = '<span class="text-xs px-2 py-1 bg-green-100 text-green-700 rounded-full">已完成</span>';
    } else {
         statusBadge = '<span class="text-xs px-2 py-1 bg-gray-100 text-gray-500 rounded-full">未开始</span>';
    }

    const div = document.createElement('div');
    div.className = 'bg-white p-6 rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-all animate-fade-in';
    div.style.animationDelay = `${i * 0.05}s`;
    
    let imagesHtml = '';
    if (images.length > 0) {
        // Show only last 4 images (reversed: newest first)
        const displayImages = images.slice(-4).reverse();
        
        imagesHtml = `<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
           ${displayImages.map(path => {
               // Use normalizePath to handle absolute/relative paths correctly
               const url = normalizePath(path);
               return `
                 <div class="relative group aspect-video rounded-lg overflow-hidden cursor-zoom-in border border-gray-100" onclick="zoomImage('${url}')">
                   <img src="${url}" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" loading="lazy">
                   <div class="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors"></div>
                 </div>
               `;
           }).join('')}
        </div>`;
    } else if (isShotProcessing) {
        // Show Skeleton / Placeholder
        imagesHtml = `
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
             ${[1,2].map(() => `
               <div class="aspect-video rounded-lg bg-gray-100 animate-pulse flex items-center justify-center">
                 <svg class="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                 </svg>
               </div>
             `).join('')}
          </div>
        `;
    } else {
        imagesHtml = '<div class="text-gray-400 text-sm italic py-4">暂无生成的图片</div>';
    }

    // Find shot info to get character/scene
    const shot = p.storyboard?.shots?.find(s => s.shot_number === i);
    let refInfoHtml = '';
    
    if (shot) {
        let refs = [];
        // Character (Support multiple or single but data model is single for now, but prompts might mention multiple)
        // Check "character" field first
        if (shot.character) {
            const char = p.characters?.find(c => c.name === shot.character);
            if (char) {
                const img = char.image_path ? 
                    `<div class="relative group cursor-zoom-in" onclick="zoomImage('${normalizePath(char.image_path)}')">
                        <img src="${normalizePath(char.image_path)}" class="w-8 h-8 rounded-full object-cover border border-gray-200" title="参考图">
                        <div class="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 rounded-full transition-opacity"></div>
                     </div>` : 
                    '<span class="text-xs text-gray-300">无图</span>';
                
                refs.push(`
                    <div class="flex items-center space-x-2 bg-gray-50 px-2 py-1 rounded text-xs border border-gray-100">
                        <span class="text-gray-500 font-bold">角色:</span>
                        <span class="text-gray-700 truncate max-w-[100px]" title="${escapeHtml(shot.character)}">${escapeHtml(shot.character)}</span>
                        ${img}
                    </div>
                `);
            }
        }

        // Also check if any other characters are mentioned in prompt? 
        // For now, let's just stick to structured data. 
        // User asked to show ALL important characters if mentioned.
        // But we only have shot.character (single) in current data model.
        // We might need to scan the prompt or update backend to support multiple characters per shot.
        // As a workaround, we can check if any OTHER character names appear in the description or prompt.
        if (p.characters) {
            p.characters.forEach(c => {
                if (c.name !== shot.character && (shot.description?.includes(c.name) || shot.dialogue?.includes(c.name))) {
                     const img = c.image_path ? 
                        `<div class="relative group cursor-zoom-in" onclick="zoomImage('${normalizePath(c.image_path)}')">
                            <img src="${normalizePath(c.image_path)}" class="w-8 h-8 rounded-full object-cover border border-gray-200" title="参考图">
                            <div class="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 rounded-full transition-opacity"></div>
                         </div>` : 
                        '<span class="text-xs text-gray-300">无图</span>';
                     
                     refs.push(`
                        <div class="flex items-center space-x-2 bg-gray-50 px-2 py-1 rounded text-xs border border-gray-100">
                            <span class="text-gray-500 font-bold">角色:</span>
                            <span class="text-gray-700 truncate max-w-[100px]" title="${escapeHtml(c.name)}">${escapeHtml(c.name)}</span>
                            ${img}
                        </div>
                    `);
                }
            });
        }

        // Scene
        // Fallback: Check if scene field is present or scan description/dialogue/prompt
        let sceneName = shot.scene;
        let validScene = null;

        // 1. Try explicit scene name
        if (sceneName && p.scenes) {
             validScene = p.scenes.find(s => s.name === sceneName);
        }
        
        // 2. Scan logic if shot.scene is missing OR invalid, but user expects it from description
        if (!validScene && p.scenes) {
             // Find any scene name OR location that appears in description/dialogue or PROMPT (prioritized)
             validScene = p.scenes.find(s => 
                 (s.name && (
                     (promptText && promptText.includes(s.name)) ||
                     (shot.description && shot.description.includes(s.name)) || 
                     (shot.dialogue && shot.dialogue.includes(s.name))
                 )) || 
                 (s.location && (
                     (promptText && promptText.includes(s.location)) ||
                     (shot.description && shot.description.includes(s.location)) || 
                     (shot.dialogue && shot.dialogue.includes(s.location))
                 ))
             );
             if (validScene) {
                 sceneName = validScene.name;
             }
        }

        if (sceneName) {
            const scene = validScene || p.scenes?.find(s => s.name === sceneName);
            if (scene) {
                const img = scene.image_path ? 
                    `<div class="relative group cursor-zoom-in" onclick="zoomImage('${normalizePath(scene.image_path)}')">
                        <img src="${normalizePath(scene.image_path)}" class="w-8 h-8 rounded-full object-cover border border-gray-200" title="参考图">
                        <div class="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 rounded-full transition-opacity"></div>
                     </div>` : 
                    '<span class="text-xs text-gray-300">无图</span>';
                    
                refs.push(`
                    <div class="flex items-center space-x-2 bg-gray-50 px-2 py-1 rounded text-xs border border-gray-100">
                        <span class="text-gray-500 font-bold">场景:</span>
                        <span class="text-gray-700 truncate max-w-[100px]" title="${escapeHtml(sceneName)}">${escapeHtml(sceneName)}</span>
                        ${img}
                    </div>
                `);
            }
        }
        if (refs.length > 0) {
            refInfoHtml = `<div class="flex flex-wrap gap-3 mb-4 pt-2 border-t border-gray-50">${refs.join('')}</div>`;
        }
    }

    div.innerHTML = `
      <div class="flex justify-between items-center mb-4 border-b border-gray-100 pb-3">
        <div class="font-bold text-lg text-blue-600 flex items-center">
          <span class="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm mr-3">#${i}</span>
          镜头 ${i}
          <div class="ml-4">${statusBadge}</div>
        </div>
        <div class="flex items-center space-x-3">
           <button onclick="checkShotStatus()" class="px-3 py-1.5 rounded-lg bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 text-sm font-medium transition-colors flex items-center" title="刷新状态">
             <span class="mr-1">🔍</span> 状态
           </button>
           <select class="text-sm border border-gray-200 rounded-lg px-2 py-1 bg-gray-50 outline-none focus:border-blue-500 appearance-none pr-6 bg-[url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%2364748b%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E')] bg-[length:8px_8px] bg-[right:0.5rem_center] bg-no-repeat" id="regenCount_${i}">
              <option value="1">生成 1 张</option>
              <option value="2">生成 2 张</option>
              <option value="3">生成 3 张</option>
              <option value="4">生成 4 张</option>
           </select>
           <button class="px-3 py-1.5 bg-gray-50 text-gray-600 rounded-lg text-xs hover:bg-gray-100 flex items-center border border-gray-200 transition-colors"
               onclick="triggerImageUpload(${i})">
               <svg class="w-3.5 h-3.5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
               </svg>
               上传首图
           </button>
           <input type="file" id="upload-input-${i}" style="display: none" accept="image/png,image/jpeg,image/jpg" onchange="uploadShotImage(${i}, this)">
           <button onclick="regenerateShotImage(${i})" class="px-3 py-1.5 rounded-lg bg-white border border-blue-200 text-blue-600 hover:bg-blue-50 text-sm font-medium transition-colors flex items-center">
             <span class="mr-1">🔄</span> 重新生成
           </button>
        </div>
      </div>
      
      ${refInfoHtml}
      
      <div class="mb-4">
          <div class="flex items-center justify-between mb-1">
              <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider">分镜首图提示词</label>
              <button onclick="saveShotPrompt(${i}, 'image')" class="text-xs text-blue-600 hover:text-blue-800 font-medium">保存提示词</button>
          </div>
          <textarea id="imgPrompt_${i}" class="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:border-blue-500 outline-none h-24 resize-none">${escapeHtml(promptText)}</textarea>
      </div>

      ${imagesHtml}
    `;
    imagesEl.appendChild(div);
  }
}

function zoomImage(url) {
    imgZoomContent.src = url;
    imgZoomModal.classList.remove('hidden');
    // small delay to allow display:block to apply before opacity transition
    setTimeout(() => imgZoomModal.classList.add('opacity-100'), 10);
}

function triggerImageUpload(shotNumber) {
    document.getElementById(`upload-input-${shotNumber}`).click();
}

async function uploadShotImage(shotNumber, input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    
    // Reset input
    input.value = '';
    
    const formData = new FormData();
    formData.append('file', file);
    
    updateStatus(`正在上传镜头 ${shotNumber} 的首图...`, 'blue');
    setInteractionState(false);
    
    try {
        const res = await fetch(`/api/projects/${projectId}/images/${shotNumber}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) {
            let errorMsg;
            try {
                // Clone response before reading, just in case
                const clone = res.clone();
                try {
                    const err = await res.json();
                    errorMsg = err.error || '上传失败';
                } catch {
                    // JSON parse failed, try text from clone
                    const text = await clone.text();
                    errorMsg = `上传失败 (${res.status}): ${text.substring(0, 100)}`;
                }
            } catch (e) {
                // If cloning or everything fails
                 errorMsg = `上传失败 (${res.status})`;
            }
            throw new Error(errorMsg);
        }
        
        const data = await res.json();
        
        await loadProject(projectId, false);
        updateStatus(`镜头 ${shotNumber} 首图上传成功`, 'green');
    } catch (e) {
        updateStatus(`上传失败: ${e.message}`, 'red');
        console.error(e);
    } finally {
        setInteractionState(true);
    }
}

async function regenerateShotImage(shotNumber) {
    const count = parseInt(document.getElementById(`regenCount_${shotNumber}`).value) || 1;
    const promptVal = document.getElementById(`imgPrompt_${shotNumber}`).value;
    
    updateStatus(`正在重新生成镜头 ${shotNumber} 的首图 (${count}张)...`, 'blue');
    setInteractionState(false);
    
    try {
        const res = await fetch(`/api/projects/${projectId}/images/${shotNumber}`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_count: count, prompt: promptVal })
        });
        
        if (!res.ok) throw new Error('生成失败');
        
        await loadProject(projectId, false);
        updateStatus(`镜头 ${shotNumber} 首图生成完成`, 'green');
    } catch (e) {
        updateStatus(`生成失败: ${e.message}`, 'red');
    } finally {
        setInteractionState(true);
    }
}

function renderVideos(p) {
  videosEl.innerHTML = '';
  const paths = p.video_paths || [];
  const imgPaths = p.image_paths || [];
  
  // Ensure we have a working dictionary
  const shotImages = p.shot_images ? JSON.parse(JSON.stringify(p.shot_images)) : {};
  // Sync from image_paths (legacy/current status source) to ensure we have at least the selected image
  if (p.image_paths) {
     p.image_paths.forEach((path, i) => {
         const shotNum = i + 1;
         if (path) {
             if (!shotImages[shotNum]) {
                 shotImages[shotNum] = [];
             }
             // Add if not present
             if (!shotImages[shotNum].includes(path)) {
                 shotImages[shotNum].push(path);
             }
         }
     });
  }

  const vidPrompts = p.video_prompts || [];

  const shotsCount = p.storyboard?.shots?.length || 0;
  if (shotsCount === 0) {
      videosEl.innerHTML = '<div class="text-gray-400 text-center py-10">请先生成分镜</div>';
      return;
  }

  // If generating or has videos, render list
  const isGlobalProcessing = p.status === 'in_progress' || (currentProject && currentProject.status === 'in_progress');
  if (paths.length === 0 && !isGlobalProcessing && !p.video_prompts) {
    videosEl.innerHTML = '<div class="text-gray-400 text-center py-10">点击上方按钮生成视频</div>';
    return;
  }

  for (let i = 1; i <= shotsCount; i++) {
    const shotNum = i;
    // Video path (by index, assuming order matches shots)
    const path = paths[i-1];
    const url = normalizePath(path);
    
    // Video Prompt
    const currentVidPrompt = vidPrompts.find(pr => pr.shot_number === shotNum) || vidPrompts[i-1] || {};
    const vidPromptText = currentVidPrompt.video_prompt || '';
    
    // Image candidates
    const allCandidates = shotImages[shotNum] || [];
    // Show only last 4, reversed (newest first)
    const candidates = allCandidates.slice(-4).reverse();
    
    // Default logic: Use current selection (source of truth), fallback to latest candidate (first in reversed list)
    let currentImagePath = imgPaths[i-1];
    if (!currentImagePath && candidates.length > 0) {
        currentImagePath = candidates[0];
    }

    // Check status
    const statusKey = `shot_status_video_${shotNum}`;
    const statusVal = p[statusKey];
    let statusBadge = '';
    let isShotProcessing = false;

    if (statusVal === 'processing') {
         statusBadge = '<span class="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-full animate-pulse">生成中...</span>';
         isShotProcessing = true;
    } else if (statusVal === 'failed') {
         statusBadge = '<span class="text-xs px-2 py-1 bg-red-100 text-red-700 rounded-full">生成失败</span>';
    } else if (statusVal === 'completed' || url) {
         statusBadge = '<span class="text-xs px-2 py-1 bg-green-100 text-green-700 rounded-full">已完成</span>';
    } else {
         statusBadge = '<span class="text-xs px-2 py-1 bg-gray-100 text-gray-500 rounded-full">未开始</span>';
    }

    const div = document.createElement('div');
    div.className = 'bg-white p-6 rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-all animate-fade-in';
    div.style.animationDelay = `${i * 0.05}s`;
    
    const candidatesHtml = candidates.map(cPath => {
        const isSelected = cPath === currentImagePath;
        const cUrl = normalizePath(cPath);
        return `
          <div class="relative group cursor-pointer rounded overflow-hidden border-2 ${isSelected ? 'border-blue-500 ring-2 ring-blue-200' : 'border-transparent'}" 
               onclick="selectVideoImage(${shotNum}, '${escapeHtml(cPath.replace(/'/g, "\\'"))}')">
             <img src="${cUrl}" class="w-full h-full object-cover">
             ${isSelected ? '<div class="absolute top-1 right-1 w-4 h-4 bg-blue-500 rounded-full text-white flex items-center justify-center text-xs">✓</div>' : ''}
             <div class="absolute bottom-1 right-1 w-6 h-6 bg-black/50 hover:bg-black/70 rounded-full text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  title="放大预览" onclick="event.stopPropagation(); zoomImage('${cUrl}')">
                 <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" /></svg>
             </div>
          </div>
        `;
    }).join('');

    let videoContent = '';
    if (url) {
        videoContent = `
           <video controls class="w-full rounded-lg shadow-sm max-h-[300px]">
              <source src="${url}" type="video/mp4">
              您的浏览器不支持 Video 标签
           </video>`;
    } else if (isShotProcessing) {
        videoContent = `
           <div class="w-full h-[240px] bg-gray-100 rounded-lg animate-pulse flex flex-col items-center justify-center text-gray-400">
               <span class="text-3xl mb-2">🎥</span>
               <span class="text-sm">视频生成中...</span>
           </div>
        `;
    } else {
        videoContent = `
           <div class="flex flex-col items-center text-gray-400">
              <span class="text-3xl mb-2">🎬</span>
              <span class="text-sm">暂无视频 / 生成失败</span>
           </div>`;
    }

    // Generate placeholders if fewer than 4 candidates
    const placeholdersCount = Math.max(0, 4 - candidates.length);
    const placeholdersHtml = Array(placeholdersCount).fill(0).map(() => `
        <div class="aspect-video rounded bg-gray-100 border-2 border-dashed border-gray-200 flex items-center justify-center text-gray-300">
            <span class="text-xs">空</span>
        </div>
    `).join('');

    div.innerHTML = `
      <div class="flex items-center justify-between mb-4 border-b border-gray-100 pb-3">
         <div class="font-bold text-lg text-blue-600 flex items-center">
            <span class="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm mr-3">#${shotNum}</span>
            镜头 ${shotNum}
            <div class="ml-4">${statusBadge}</div>
         </div>
         <div class="flex items-center space-x-3">
            <button onclick="checkShotStatus()" class="px-3 py-1.5 rounded-lg bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 text-sm font-medium transition-colors flex items-center" title="刷新状态">
                <span class="mr-1">🔍</span> 状态
            </button>
            <button onclick="regenerateShotVideo(${shotNum})" class="px-3 py-1.5 rounded-lg bg-white border border-blue-200 text-blue-600 hover:bg-blue-50 text-sm font-medium transition-colors flex items-center">
                <span class="mr-1">🎥</span> 重新生成视频
            </button>
         </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="space-y-4">
              <div>
                  <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">首图选择 (最新4张)</label>
                  <div class="grid grid-cols-4 gap-2 p-2 bg-gray-50 rounded-lg border border-gray-200">
                      ${candidatesHtml}
                      ${placeholdersHtml}
                  </div>
                  ${candidates.length === 0 ? '<div class="text-xs text-gray-400 mt-1">暂无生成的首图，请到"分镜首图"页面生成</div>' : ''}
                  <input type="hidden" id="vidImgPath_${shotNum}" value="${escapeHtml(currentImagePath || '')}">
              </div>
              <div>
                  <div class="flex items-center justify-between mb-1">
                      <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider">分镜视频提示词</label>
                      <button onclick="saveShotPrompt(${shotNum}, 'video')" class="text-xs text-blue-600 hover:text-blue-800 font-medium">保存提示词</button>
                  </div>
                  <textarea id="vidPrompt_${shotNum}" class="w-full bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm focus:border-blue-500 outline-none h-24 resize-none">${escapeHtml(vidPromptText)}</textarea>
              </div>
          </div>
          
          <div class="flex flex-col items-center justify-center bg-gray-100 rounded-xl min-h-[240px] relative">
               ${videoContent}
          </div>
      </div>
    `;
    videosEl.appendChild(div);
  }
}

window.selectVideoImage = function(shotNum, path) {
    document.getElementById(`vidImgPath_${shotNum}`).value = path;
    
    // Update UI
    const container = document.getElementById(`vidImgPath_${shotNum}`).previousElementSibling; // The grid div
    const cards = container.children;
    
    for (let card of cards) {
        // We need to know which card corresponds to this path. 
        // We can check the onclick attribute or img src.
        // Path passed is raw path. Img src has / prepended usually.
        const img = card.querySelector('img');
        const src = img.getAttribute('src');
        const match = src === normalizePath(path);
        
        if (match) {
            card.className = 'relative cursor-pointer rounded overflow-hidden border-2 border-blue-500 ring-2 ring-blue-200';
            if (!card.querySelector('.absolute')) {
                card.insertAdjacentHTML('beforeend', '<div class="absolute top-1 right-1 w-4 h-4 bg-blue-500 rounded-full text-white flex items-center justify-center text-xs">✓</div>');
            }
        } else {
            card.className = 'relative cursor-pointer rounded overflow-hidden border-2 border-transparent';
            const badge = card.querySelector('.absolute');
            if (badge) badge.remove();
        }
    }
};

window.saveShotPrompt = async function(shotNum, type) {
    const id = type === 'image' ? `imgPrompt_${shotNum}` : `vidPrompt_${shotNum}`;
    const promptVal = document.getElementById(id).value;
    
    if (!promptVal) return;
    
    // Optimistic UI feedback could be nice, but simple alert/status for now
    updateStatus(`正在保存镜头 ${shotNum} 的${type === 'image' ? '首图' : '视频'}提示词...`, 'blue');
    
    try {
        const res = await fetch(`/api/projects/${projectId}/prompts/${shotNum}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: type, prompt: promptVal })
        });
        
        if (!res.ok) throw new Error('保存失败');
        
        updateStatus(`镜头 ${shotNum} 提示词已保存`, 'green');
    } catch (e) {
        updateStatus(`保存失败: ${e.message}`, 'red');
    }
};



window.selectVideoImage = async function(shotNum, path) {
    if (!projectId) return;
    
    // Update hidden input
    const imgPathInput = document.getElementById(`vidImgPath_${shotNum}`);
    if (imgPathInput) imgPathInput.value = path;
    
    // Update UI selection
    const container = document.getElementById(`vidCandidates_${shotNum}`);
    if (container) {
        const children = container.children;
        for (let child of children) {
             const img = child.querySelector('img');
             // Use decodeURIComponent to handle encoded slashes if any, though normalizePath usually handles it
             // Simple string match on src attribute
             if (img && img.getAttribute('src').includes(encodeURIComponent(path.split('/').pop()))) {
                 child.classList.add('border-blue-500', 'ring-2', 'ring-blue-200');
                 child.classList.remove('border-transparent');
                 // Add checkmark if not exists
                 if (!child.querySelector('.selection-badge')) {
                      const badge = document.createElement('div');
                      badge.className = 'selection-badge absolute top-1 right-1 w-4 h-4 bg-blue-500 rounded-full text-white flex items-center justify-center text-xs';
                      badge.textContent = '✓';
                      child.appendChild(badge);
                 }
             } else {
                 child.classList.remove('border-blue-500', 'ring-2', 'ring-blue-200');
                 child.classList.add('border-transparent');
                 // Remove checkmark
                 const badge = child.querySelector('.selection-badge');
                 if (badge) badge.remove();
             }
        }
    }

    try {
        // Persist selection to backend
        await fetch(`/api/projects/${projectId}/images/${shotNum}/select`, {
             method: 'POST',
             headers: { 'Content-Type': 'application/json' },
             body: JSON.stringify({ path: path })
        });
    } catch (e) {
        console.error('Failed to select image', e);
    }
};

async function regenerateShotVideo(shotNum) {
    const promptVal = document.getElementById(`vidPrompt_${shotNum}`).value;
    const imgPath = document.getElementById(`vidImgPath_${shotNum}`).value;
    
    if (!imgPath) {
        alert('请选择一张首图');
        return;
    }
    
    updateStatus(`正在重新生成镜头 ${shotNum} 的视频...`, 'blue');
    setInteractionState(false);
    
    try {
        const res = await fetch(`/api/projects/${projectId}/videos/${shotNum}`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                video_prompt: promptVal,
                image_path: imgPath
            })
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error('生成失败');
        
        if (data.task_id) {
            updateStatus(`视频生成中... Task ID: ${data.task_id}`, 'blue');
            startPolling(data.task_id);
        } else {
            await loadProject(projectId, false);
            updateStatus(`镜头 ${shotNum} 视频生成完成`, 'green');
        }
    } catch (e) {
        updateStatus(`生成失败: ${e.message}`, 'red');
    } finally {
        setInteractionState(true);
    }
}

function renderOutput(p) {
  finalVideoEl.innerHTML = '';
  
  if (p.final_video) {
    const url = normalizePath(p.final_video);
    finalVideoEl.innerHTML = `
      <div class="text-center w-full">
        <video controls class="w-full max-w-4xl mx-auto rounded-xl shadow-2xl mb-8 border-4 border-white">
          <source src="${url}" type="video/mp4">
          您的浏览器不支持 Video 标签
        </video>
        <div class="flex justify-center space-x-4">
          <button id="btnRemerge" class="px-8 py-3 rounded-lg bg-blue-600 text-white hover:bg-blue-700 text-lg font-medium shadow-lg shadow-blue-200 transition-all flex items-center">
            <span class="mr-2">🔄</span> 重新拼接
          </button>
          <a href="${url}" download class="px-8 py-3 rounded-lg bg-green-600 text-white hover:bg-green-700 text-lg font-medium shadow-lg shadow-green-200 transition-all flex items-center">
            <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
            下载完整视频
          </a>
        </div>
      </div>
    `;
    
    // Bind remerge button
    document.getElementById('btnRemerge').addEventListener('click', () => callStep('merge'));
    
  } else {
    // Check if we have video paths to merge
    const hasVideos = p.video_paths && p.video_paths.length > 0;
    
    if (hasVideos) {
        finalVideoEl.innerHTML = `
          <div class="text-center w-full py-10">
             <div class="mb-6 text-gray-500">所有分镜视频已就绪，点击下方按钮生成最终成品</div>
             <button id="btnStartMerge" class="px-8 py-3 rounded-lg bg-blue-600 text-white hover:bg-blue-700 text-lg font-medium shadow-lg shadow-blue-200 transition-all flex items-center mx-auto">
                <span class="mr-2">🎬</span> 开始拼接成片
             </button>
          </div>
        `;
        document.getElementById('btnStartMerge').addEventListener('click', () => callStep('merge'));
    } else {
        finalVideoEl.innerHTML = '<div class="text-gray-400">暂无最终成品，请先生成分镜视频</div>';
    }
  }
}

// Settings Logic
let currentSettingsConfig = null;

function renderPlatformSettings(platform) {
    if (!currentSettingsConfig || !currentSettingsConfig.platforms) return;
    
    const pConf = currentSettingsConfig.platforms[platform] || {};
    
    // Auth
    document.getElementById('conf_ak').value = pConf.access_key || '';
    document.getElementById('conf_sk').value = pConf.secret_key || '';
    const arkKey = document.getElementById('conf_ark_key');
    if (arkKey) arkKey.value = pConf.ark_api_key || '';

    // Models
    const models = pConf.models || {};
    document.getElementById('conf_llm').value = models.llm?.model_id || '';
    document.getElementById('conf_img').value = models.image?.model_id || '';
    document.getElementById('conf_vid').value = models.video?.model_id || '';

    // TOS
    const tos = pConf.tos || {};
    document.getElementById('conf_tos_enable').checked = tos.enable || false;
    document.getElementById('conf_tos_endpoint').value = tos.endpoint || '';
    document.getElementById('conf_tos_region').value = tos.region || '';
    
    // Update placeholders based on platform
    const isBytePlus = platform === 'byteplus';
    document.getElementById('conf_tos_endpoint').placeholder = isBytePlus ? 'tos.ap-southeast-1.bytepluses.com' : 'tos-cn-beijing.volces.com';
    document.getElementById('conf_tos_region').placeholder = isBytePlus ? 'ap-southeast-1' : 'cn-beijing';
    
    // Load Buckets (Try to select current if available)
    loadBuckets(tos.bucket_name, tos.bucket_directory);
}

function toggleSettingsEdit(editable) {
    const modal = document.getElementById('settingsModal');
    if (!modal) return;
    const inputs = modal.querySelectorAll('input, select, textarea');
    inputs.forEach(el => {
        if (el.id === 'conf_platform') return;
        
        el.disabled = !editable;
        if (!editable) {
            el.classList.add('bg-gray-100', 'text-gray-500');
            el.classList.remove('bg-white', 'text-gray-900');
        } else {
            el.classList.remove('bg-gray-100', 'text-gray-500');
            el.classList.add('bg-white', 'text-gray-900');
        }
    });

    const saveBtn = document.getElementById('saveSettings');
    const editBtn = document.getElementById('editSettings');
    const closeBtn = document.getElementById('cancelSettings');
    
    const allowEdit = currentSettingsConfig?.app?.allow_settings_edit === true;

    if (editable) {
        if(saveBtn) saveBtn.classList.remove('hidden');
        if(editBtn) editBtn.classList.add('hidden');
        if(closeBtn) closeBtn.textContent = '取消';
    } else {
        if(saveBtn) saveBtn.classList.add('hidden');
        // Only show Edit button if allowed
        if(editBtn) {
            if (allowEdit) {
                editBtn.classList.remove('hidden');
            } else {
                editBtn.classList.add('hidden');
            }
        }
        if(closeBtn) closeBtn.textContent = '关闭';
    }
}

async function openSettings() {
  settingsModal.classList.remove('hidden');
  toggleSettingsEdit(false);
  try {
    const resConf = await fetch('/api/config');
    currentSettingsConfig = await resConf.json();
    
    // Refresh UI state with new config (e.g. show/hide Edit button)
    toggleSettingsEdit(false);
    
    const currentPlatform = currentSettingsConfig.platform || 'volcengine';
    const platformSelect = document.getElementById('conf_platform');
    if (platformSelect) {
        platformSelect.value = currentPlatform;
    }
    
    renderPlatformSettings(currentPlatform);

    // Load Prompts
    const resPrompts = await fetch('/api/prompts');
    const prompts = await resPrompts.json();
    
    document.getElementById('conf_prompt_script_sys').value = prompts.script_generation?.system || '';
    document.getElementById('conf_prompt_sb_sys').value = prompts.storyboard_generation?.system || '';
    document.getElementById('conf_prompt_img_sys').value = prompts.image_prompt_generation?.system || '';
    document.getElementById('conf_prompt_vid_sys').value = prompts.video_prompt_generation?.system || '';
    document.getElementById('conf_prompt_script_opt_sys').value = prompts.script_optimization?.system || '';
    document.getElementById('conf_prompt_sb_opt_sys').value = prompts.storyboard_optimization?.system || '';
    document.getElementById('conf_prompt_char_design_sys').value = prompts.character_design?.system || '';
    document.getElementById('conf_prompt_char_gen_sys').value = prompts.character_prompt_generation?.system || '';
    document.getElementById('conf_prompt_scene_design_sys').value = prompts.scene_design?.system || '';
    document.getElementById('conf_prompt_scene_gen_sys').value = prompts.scene_prompt_generation?.system || '';

  } catch (e) {
    console.error('Load settings failed', e);
  }
}

async function loadBuckets(currentBucket, currentDir) {
    const bucketSelect = document.getElementById('conf_tos_bucket');
    bucketSelect.innerHTML = '<option value="" disabled selected>加载中...</option>';
    
    // Clear directory select
    const dirSelect = document.getElementById('conf_tos_directory');
    if (dirSelect) dirSelect.innerHTML = '<option value="" disabled selected>请先选择存储桶</option>';
    
    try {
        const ak = document.getElementById('conf_ak')?.value || '';
        const sk = document.getElementById('conf_sk')?.value || '';
        const endpoint = document.getElementById('conf_tos_endpoint')?.value || '';
        const region = document.getElementById('conf_tos_region')?.value || '';
        const platform = document.getElementById('conf_platform')?.value || '';

        // Always use POST to support overriding credentials
        const res = await fetch('/api/buckets', {
             method: 'POST',
             headers: {'Content-Type': 'application/json'},
             body: JSON.stringify({
                 access_key: ak,
                 secret_key: sk,
                 endpoint: endpoint,
                 region: region,
                 platform: platform
             })
        });
        const data = await res.json();
        
        bucketSelect.innerHTML = '<option value="" disabled selected>选择存储桶</option>';
        
        if (data.buckets && data.buckets.length > 0) {
            data.buckets.forEach(b => {
                const opt = document.createElement('option');
                opt.value = b.name;
                opt.textContent = `${b.name} (${b.location})`;
                if (b.name === currentBucket) opt.selected = true;
                bucketSelect.appendChild(opt);
            });
            
            // If we have a selected bucket, load directories
            if (currentBucket) {
                await loadDirectories(currentBucket, currentDir);
            }
            
            // Add change listener to load directories
            bucketSelect.onchange = (e) => loadDirectories(e.target.value);
            
        } else {
             const opt = document.createElement('option');
             opt.disabled = true;
             opt.textContent = '未找到存储桶或无权限';
             bucketSelect.appendChild(opt);
        }
    } catch (e) {
        console.error('Failed to list buckets', e);
        bucketSelect.innerHTML = '<option value="" disabled>加载失败</option>';
    }
}

async function loadDirectories(bucketName, currentDir) {
    const dirSelect = document.getElementById('conf_tos_directory');
    if (!dirSelect) return;
    
    dirSelect.innerHTML = '<option value="" disabled selected>加载目录中...</option>';
    
    try {
        const res = await fetch(`/api/buckets/${bucketName}/directories`);
        const data = await res.json();
        
        dirSelect.innerHTML = '<option value="">根目录</option>';
        
        if (data.directories) {
            data.directories.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d;
                opt.textContent = d;
                if (d === currentDir || d === currentDir + '/') opt.selected = true;
                dirSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.error('Failed to list directories', e);
        dirSelect.innerHTML = '<option value="" disabled>加载失败</option>';
    }
}

async function createNewDirectory() {
    const bucketSelect = document.getElementById('conf_tos_bucket');
    const bucketName = bucketSelect.value;
    if (!bucketName) {
        alert('请先选择存储桶');
        return;
    }
    
    const newDir = prompt("请输入新目录名称 (例如: my-project/):");
    if (!newDir) return;
    
    try {
        const res = await fetch(`/api/buckets/${bucketName}/directories`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ directory: newDir })
        });
        
        if (!res.ok) throw new Error('创建失败');
        
        // Reload directories and select new one
        await loadDirectories(bucketName, newDir.endsWith('/') ? newDir : newDir + '/');
        alert('目录创建成功');
    } catch (e) {
        alert('错误: ' + e.message);
    }
}

async function saveConfig() {
  saveSettings.disabled = true;
  saveSettings.textContent = '保存中...';
  try {
    const platform = document.getElementById('conf_platform').value;
    const base = `platforms.${platform}`;
    
    // Save Main Config
    const confUpdate = {
      'platform': platform,
      [`${base}.ark_api_key`]: document.getElementById('conf_ark_key').value.trim(),
      [`${base}.access_key`]: document.getElementById('conf_ak').value.trim(),
      [`${base}.secret_key`]: document.getElementById('conf_sk').value.trim(),
      [`${base}.models.llm.model_id`]: document.getElementById('conf_llm').value.trim(),
      [`${base}.models.image.model_id`]: document.getElementById('conf_img').value.trim(),
      [`${base}.models.video.model_id`]: document.getElementById('conf_vid').value.trim(),
      [`${base}.tos.enable`]: document.getElementById('conf_tos_enable').checked,
      [`${base}.tos.endpoint`]: document.getElementById('conf_tos_endpoint').value.trim(),
      [`${base}.tos.region`]: document.getElementById('conf_tos_region').value.trim(),
      // Only update bucket/dir if user selected something (might be disabled if cross-platform)
      // If select is empty/disabled, don't overwrite with empty string if we want to keep existing?
      // Actually, if renderPlatformSettings populated it with current value, we are fine.
      // If it populated with empty, we might overwrite.
      // Let's check value.
    };
    
    const bucketVal = document.getElementById('conf_tos_bucket').value;
    const dirVal = document.getElementById('conf_tos_directory').value;
    if (bucketVal) confUpdate[`${base}.tos.bucket_name`] = bucketVal;
    if (dirVal) confUpdate[`${base}.tos.bucket_directory`] = dirVal;

    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(confUpdate)
    });

    // Save Prompts
    const promptsUpdate = {
      'script_generation.system': document.getElementById('conf_prompt_script_sys').value,
      'storyboard_generation.system': document.getElementById('conf_prompt_sb_sys').value,
      'image_prompt_generation.system': document.getElementById('conf_prompt_img_sys').value,
      'video_prompt_generation.system': document.getElementById('conf_prompt_vid_sys').value,
      'script_optimization.system': document.getElementById('conf_prompt_script_opt_sys').value,
      'storyboard_optimization.system': document.getElementById('conf_prompt_sb_opt_sys').value,
      'character_design.system': document.getElementById('conf_prompt_char_design_sys').value,
      'character_prompt_generation.system': document.getElementById('conf_prompt_char_gen_sys').value,
      'scene_design.system': document.getElementById('conf_prompt_scene_design_sys').value,
      'scene_prompt_generation.system': document.getElementById('conf_prompt_scene_gen_sys').value,
    };
    await fetch('/api/prompts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(promptsUpdate)
    });

    settingsModal.classList.add('hidden');
    alert('设置已保存');
    
    // Reload to refresh global state
    window.location.reload();
    
  } catch (e) {
    alert('保存失败: ' + e.message);
  } finally {
    saveSettings.disabled = false;
    saveSettings.textContent = '保存更改';
  }
}

// Project Manager Modal Logic
document.addEventListener('DOMContentLoaded', () => {
    // Basic search input in sidebar
    const searchInput = document.getElementById('historySearch');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                loadHistory();
            }, 500);
        });
    }
    
    // Toggle Button to open Project Manager Modal
    const toggleFilterBtn = document.getElementById('toggleFilter');
    const pmModal = document.getElementById('projectManagerModal');
    const closePmBtn = document.getElementById('closeProjectManager');
    
    if (toggleFilterBtn && pmModal) {
        toggleFilterBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            pmModal.classList.remove('hidden');
            loadProjectManagerData();
        });
    }
    
    if (closePmBtn && pmModal) {
        closePmBtn.addEventListener('click', () => {
            pmModal.classList.add('hidden');
        });
    }
    
    // Event listeners for PM filters
    const pmFilters = ['pmSearch', 'pmFilterStatus', 'pmFilterPlatform', 'pmFilterInputType', 'pmFilterRatio', 'pmFilterResolution'];
    let pmDebounceTimer;
    
    pmFilters.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', () => {
                clearTimeout(pmDebounceTimer);
                pmDebounceTimer = setTimeout(() => {
                    loadProjectManagerData();
                }, 300);
            });
        }
    });
    
    document.getElementById('pmResetFilter')?.addEventListener('click', () => {
        pmFilters.forEach(id => {
            const el = document.getElementById(id);
            if(el) el.value = '';
        });
        loadProjectManagerData();
    });

    document.getElementById('editSettings')?.addEventListener('click', () => {
        toggleSettingsEdit(true);
    });
});

async function loadProjectManagerData() {
    const pmList = document.getElementById('pmList');
    const pmEmpty = document.getElementById('pmEmpty');
    const pmLoading = document.getElementById('pmLoading');
    
    if (!pmList) return;
    
    pmLoading.classList.remove('hidden');
    pmEmpty.classList.add('hidden');
    pmList.innerHTML = '';
    
    try {
        const params = new URLSearchParams();
        const searchVal = document.getElementById('pmSearch')?.value;
        if (searchVal) params.append('name', searchVal);
        
        const status = document.getElementById('pmFilterStatus')?.value;
        if (status) params.append('status', status);
        
        const platform = document.getElementById('pmFilterPlatform')?.value;
        if (platform) params.append('platform', platform);
        
        const inputType = document.getElementById('pmFilterInputType')?.value;
        if (inputType) params.append('input_type', inputType);
        
        const ratio = document.getElementById('pmFilterRatio')?.value;
        if (ratio) params.append('aspect_ratio', ratio);
        
        const resolution = document.getElementById('pmFilterResolution')?.value;
        if (resolution) params.append('resolution', resolution);
        
        const res = await fetch(`/api/projects?${params.toString()}`);
        const data = await res.json();
        
        pmLoading.classList.add('hidden');
        
        if (data.projects && data.projects.length > 0) {
            data.projects.forEach(p => {
                const div = document.createElement('div');
                div.className = 'bg-white p-4 rounded-xl border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all cursor-pointer group';
                div.onclick = () => {
                    loadProject(p.project_id);
                    document.getElementById('projectManagerModal').classList.add('hidden');
                };
                
                const dateStr = p.created_at ? new Date(p.created_at).toLocaleString() : '未知时间';
                const statusColors = {
                    'completed': 'bg-green-100 text-green-700',
                    'processing': 'bg-blue-100 text-blue-700',
                    'failed': 'bg-red-100 text-red-700',
                    'pending': 'bg-gray-100 text-gray-700'
                };
                const statusClass = statusColors[p.status] || 'bg-gray-100 text-gray-600';
                
                // Get platform label
                const meta = p.topic_meta || {}; // Can't access meta in simple list if backend doesn't return it.
                // Wait, our backend API simple list doesn't return meta details! 
                // We need to check if backend returns enough info.
                // Let's check backend code again. Ah, `_list_projects` only returns id, name, status, created_at.
                // We need to update backend to return more info for this rich view.
                
                div.innerHTML = `
                    <div class="flex justify-between items-start mb-2">
                        <h4 class="font-bold text-gray-800 text-base truncate pr-2 group-hover:text-blue-600 transition-colors" title="${p.project_name}">${p.project_name}</h4>
                        <span class="text-xs px-2 py-1 rounded-md font-medium ${statusClass}">${p.status}</span>
                    </div>
                    <div class="flex items-center justify-between text-xs text-gray-500 mt-4">
                        <div class="flex items-center space-x-3">
                           <span class="flex items-center"><svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg> ${dateStr}</span>
                        </div>
                        <button class="opacity-0 group-hover:opacity-100 text-blue-600 font-medium hover:underline transition-all">打开项目</button>
                    </div>
                `;
                pmList.appendChild(div);
            });
        } else {
            pmEmpty.classList.remove('hidden');
        }
    } catch (e) {
        console.error('Failed to load PM data', e);
        pmLoading.classList.add('hidden');
        pmList.innerHTML = '<div class="col-span-2 text-center text-red-500 py-10">加载失败，请重试</div>';
    }
}

// Start
init();
