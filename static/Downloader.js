const formYtb = document.getElementById('downloadFormYtb');
const urlInputYtb = document.getElementById('urlYtb');
const qualitySelectYtb = document.getElementById('qualityYtb');
const audioOnlyCheckboxYtb = document.getElementById('audioOnlyYtb');
const submitBtnYtb = document.getElementById('submitBtnYtb');
const statusDivYtb = document.getElementById('statusYtb');
const downloadLinkDivYtb = document.getElementById('downloadLinkYtb');



const setDwnLoading = (isLoading) => {
  if (isLoading) {
    submitBtnYtb.disabled = true;
    submitBtnYtb.innerHTML = '<i class="ph ph-spinner animate-spin text-lg"></i><span>Processing...</span>';
    submitBtnYtb.classList.add('opacity-75');
    submitBtnYtb.style.cursor = 'not-allowed'; 
  } else {
    submitBtnYtb.disabled = false;
    submitBtnYtb.innerHTML = '<i class="ph ph-download-simple text-lg"></i><span>Download</span>';
    submitBtnYtb.classList.remove('opacity-75');
    submitBtnYtb.style.cursor = '';
  }
};

async function forceDownload(url) {
  const res = await fetch(url, { mode: 'cors' });
  if (!res.ok) throw new Error('Download failed');

  const blob = await res.blob();
  const blobUrl = window.URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = 'media.mp4'; // optional
  document.body.appendChild(a);
  a.click();

  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}
function createDirectDownloadButton(mediaUrl) {
  statusDivYtb.className = 'dark:bg-zinc-900 dark:text-gray-300 border dark:border-zinc-700 p-4 rounded-xl text-center text-sm font-medium';
  statusDivYtb.textContent = `Success! Media found on ${dataYtb.platform || 'Platform'}`;
  downloadLinkDivYtb.innerHTML = `
    <button id="directDownloadBtn"
      class="group relative flex items-center justify-center gap-4 px-5 py-2 
             font-semibold text-sm dark:text-black text-white
             bg-neutral-900 dark:bg-white border border-neutral-800
             rounded-full shadow-xl hover:-translate-y-[2px]">
      <i class="ph-bold ph-download-simple"></i>
      <span>Download Media</span>
    </button>
  `;

  document
    .getElementById('directDownloadBtn')
    .addEventListener('click', async () => {
      try {
        statusDivYtb.textContent = 'Downloading…';
        await forceDownload(mediaUrl);
        statusDivYtb.textContent = 'Download started';
      } catch (e) {
        statusDivYtb.textContent = 'Download failed';
      }
    });
}


const API_URL_Ytb = '/download'; 
formYtb.addEventListener('submit', async (e) => {
  e.preventDefault();

  const urlYtb = urlInputYtb.value.trim();
  const qualityYtb = qualitySelectYtb.value;
  const audioOnlyYtb = audioOnlyCheckboxYtb.checked;

  if (!urlYtb) return;

  setDwnLoading(true);
  statusDivYtb.className = 'dark:bg-zinc-900 dark:text-gray-300 border dark:border-zinc-700 p-4 rounded-xl text-center text-sm font-medium';
  statusDivYtb.textContent = 'Fetching video information...';
  statusDivYtb.classList.remove('hidden');
  downloadLinkDivYtb.innerHTML = '';

  try {
    const responseYtb = await fetch(API_URL_Ytb, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: urlYtb,
        quality: qualityYtb,
        audio_only: audioOnlyYtb
      })
    });

    const dataYtb = await responseYtb.json();
    if (dataYtb.download_method === "DirectURL") {
      createDirectDownloadButton(dataYtb.direct_url);
      return;
    }

    if (responseYtb.ok) {
      statusDivYtb.className = 'dark:bg-zinc-900 dark:text-gray-300 border dark:border-zinc-700 p-4 rounded-xl text-center text-sm font-medium';
      statusDivYtb.textContent = `Success! Media found on ${dataYtb.platform || 'Platform'}`;
      const fullDownloadUrl = new URL(dataYtb.download_url, window.location.origin).href;


      downloadLinkDivYtb.innerHTML = `
      <a href="${fullDownloadUrl}" download
        class="group relative flex items-center justify-center gap-4 px-5 py-2 
                font-semibold text-sm dark:text-black text-white
                bg-neutral-900 border dark:bg-white border-neutral-800
                rounded-full shadow-xl
                duration-400 ease-out
                hover:bg-neutral-800 hover:border-gray-500/50 hover:shadow-sm hover:shadow-gray-500/20
                hover:-translate-y-[2px] active:translate-y-0">
        <span class="text-xl transition-transform group-hover:scale-110">
          <i class="ph-bold ph-download-simple"></i>
        </span>
        <span class="tracking-tight">
          Save Media to Device
        </span>
        <span class="absolute inset-0 rounded-2xl bg-gradient-to-r from-transparent via-white/10 to-transparent dark:via-black/30 -translate-x-full group-hover:translate-x-full transition-transform duration-1000"></span>
      </a>
    `;
    } else {
      throw new Error(dataYtb.detail || 'Download failed');
    }
  } catch (errorYtb) {
    statusDivYtb.className = 'dark:bg-zinc-900 dark:text-gray-300 border dark:border-zinc-700 p-4 rounded-xl text-center text-sm font-medium';
    statusDivYtb.textContent = `An Error Occurred..`;
  } finally {
    setDwnLoading(false);
  }
});

// ========== Downloads Library Tab Functionality ==========

let currentDownloadsView = 'grid';
let downloadedFiles = [];

// Tab Switching - O(1)
function switchContentTab(tab) {
  const downloadTab = document.getElementById('content-tab-download');
  const libraryTab = document.getElementById('content-tab-library');
  const tabDownloadBtn = document.getElementById('tab-download');
  const tabLibraryBtn = document.getElementById('tab-library');
  const refreshBtn = document.getElementById('refresh-downloads-btn');

  if (tab === 'download') {
    downloadTab.classList.remove('hidden');
    libraryTab.classList.add('hidden');
    tabDownloadBtn.classList.add('bg-white', 'dark:bg-zinc-700', 'text-gray-900', 'dark:text-white', 'shadow-sm');
    tabDownloadBtn.classList.remove('text-gray-600', 'dark:text-gray-400');
    tabLibraryBtn.classList.remove('bg-white', 'dark:bg-zinc-700', 'text-gray-900', 'dark:text-white', 'shadow-sm');
    tabLibraryBtn.classList.add('text-gray-600', 'dark:text-gray-400');
    refreshBtn.classList.add('hidden');
    refreshBtn.classList.remove('flex');
  } else {
    downloadTab.classList.add('hidden');
    libraryTab.classList.remove('hidden');
    tabLibraryBtn.classList.add('bg-white', 'dark:bg-zinc-700', 'text-gray-900', 'dark:text-white', 'shadow-sm');
    tabLibraryBtn.classList.remove('text-gray-600', 'dark:text-gray-400');
    tabDownloadBtn.classList.remove('bg-white', 'dark:bg-zinc-700', 'text-gray-900', 'dark:text-white', 'shadow-sm');
    tabDownloadBtn.classList.add('text-gray-600', 'dark:text-gray-400');
    refreshBtn.classList.remove('hidden');
    refreshBtn.classList.add('flex');
    loadDownloadsList();
  }
  if (window.lucide) lucide.createIcons();
}

// View Toggle - O(1)
function toggleDownloadsView(view) {
  currentDownloadsView = view;
  const gridView = document.getElementById('downloads-grid');
  const listView = document.getElementById('downloads-list');
  const gridBtn = document.getElementById('view-grid-btn');
  const listBtn = document.getElementById('view-list-btn');

  if (view === 'grid') {
    gridView.classList.remove('hidden');
    listView.classList.add('hidden');
    gridBtn.classList.add('bg-gray-100', 'text-gray-700');
    gridBtn.classList.remove('text-gray-400');
    listBtn.classList.remove('bg-gray-100', 'text-gray-700');
    listBtn.classList.add('text-gray-400');
  } else {
    gridView.classList.add('hidden');
    listView.classList.remove('hidden');
    listBtn.classList.add('bg-gray-100', 'text-gray-700');
    listBtn.classList.remove('text-gray-400');
    gridBtn.classList.remove('bg-gray-100', 'text-gray-700');
    gridBtn.classList.add('text-gray-400');
  }
  renderDownloads();
}

// Fetch Downloads - O(n) where n is number of files
async function loadDownloadsList() {
  const loadingEl = document.getElementById('downloads-loading');
  const emptyEl = document.getElementById('downloads-empty');
  const gridEl = document.getElementById('downloads-grid');
  const listEl = document.getElementById('downloads-list');

  loadingEl.classList.remove('hidden');
  emptyEl.classList.add('hidden');
  gridEl.innerHTML = '';
  listEl.innerHTML = '';

  try {
    const response = await fetch('/api/downloads/list');
    const data = await response.json();

    loadingEl.classList.add('hidden');

    if (data.status === 'success' && data.files.length > 0) {
      downloadedFiles = data.files;
      document.getElementById('downloads-count').textContent = `${data.count} file${data.count !== 1 ? 's' : ''}`;
      renderDownloads();
    } else {
      emptyEl.classList.remove('hidden');
      document.getElementById('downloads-count').textContent = '0 files';
    }
  } catch (error) {
    console.error('Error loading downloads:', error);
    loadingEl.classList.add('hidden');
    emptyEl.classList.remove('hidden');
  }
}

// Render Downloads - O(n)
function renderDownloads() {
  const gridEl = document.getElementById('downloads-grid');
  const listEl = document.getElementById('downloads-list');

  gridEl.innerHTML = '';
  listEl.innerHTML = '';

  if (currentDownloadsView === 'grid') {
    downloadedFiles.forEach(file => {
      gridEl.innerHTML += createGridCard(file);
    });
  } else {
    downloadedFiles.forEach(file => {
      listEl.innerHTML += createListItem(file);
    });
  }

  if (window.lucide) lucide.createIcons();
}

// Get file icon based on type - O(1)
function getFileIcon(type) {
  const icons = {
    video: 'play-circle',
    audio: 'music',
    image: 'image',
    file: 'file'
  };
  return icons[type] || 'file';
}


function createGridCard(file) {
  const icon = getFileIcon(file.type);
  const isMedia = file.type === 'video' || file.type === 'image';
  
  return `
    <div class="group bg-white dark:bg-zinc-800 rounded-2xl border border-gray-200 dark:border-zinc-700 overflow-hidden hover:shadow-sm hover:border-gray-300 dark:hover:border-zinc-600  duration-200">
      <!-- Thumbnail/Icon Area -->
      <div class="aspect-video bg-gray-50 dark:bg-zinc-900 flex items-center justify-center relative overflow-hidden">
        ${isMedia && file.type === 'image' ? 
          `<img src="${file.download_url}" alt="${file.name}" class="w-full h-full object-cover" loading="lazy" />` :
          `<div class="w-16 h-16 text-gray-600 rounded-full flex items-center justify-center">
            <i data-lucide="${icon}" class="w-8 h-8"></i>
          </div>`
        }
        ${file.type === 'video' ? `
          <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <a href="${file.download_url}" target="_blank" class="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-lg hover:scale-110 transition-transform">
              <i data-lucide="play" class="w-5 h-5 text-gray-900 ml-0.5"></i>
            </a>
          </div>
        ` : ''}
      </div>
      
      <!-- Info -->
      <div class="p-4">
        <h4 class="font-medium text-gray-900 dark:text-white truncate text-sm mb-1" title="${file.name}">${file.name}</h4>
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-500 dark:text-gray-400">${file.size_formatted} · ${file.extension.toUpperCase()}</span>
          <span class="px-2 py-0.5 bg-white border border-gray-100 text-xs font-medium rounded-full text-gray-600">${file.type}</span>
        </div>
        
        <!-- Actions -->
        <div class="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100 dark:border-zinc-700">
          ${file.type === 'video' || file.type === 'image' ? `
            <a href="${file.download_url}" target="_blank" class="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-zinc-700 hover:bg-gray-200 dark:hover:bg-zinc-600 rounded-lg transition-colors">
              <i data-lucide="eye" class="w-3.5 h-3.5"></i>
              View
            </a>
          ` : ''}
          <a href="${file.download_url}" download class="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold text-brand bg-brand/20 hover:bg-brand/30 rounded-lg transition-colors">
            <i data-lucide="download" class="w-3.5 h-3.5"></i>
            Download
          </a>
          <button onclick="deleteDownload('${file.name}')" class="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors" title="Delete">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>
      </div>
    </div>
  `;
}


function createListItem(file) {
  const icon = getFileIcon(file.type);
  
  return `
    <div class="group flex items-center gap-4 p-4 bg-white dark:bg-zinc-800 rounded-xl border border-gray-200 dark:border-zinc-700 hover:shadow-sm hover:border-gray-300 dark:hover:border-zinc-600 ">
      <div class="w-12 h-12 text-gray-600 border border-gray-200 rounded-xl flex items-center justify-center flex-shrink-0">
        <i data-lucide="${icon}" class="w-6 h-6"></i>
      </div>
      
      <!-- Info -->
      <div class="flex-1 min-w-0">
        <h4 class="font-medium text-gray-900 dark:text-white truncate" title="${file.name}">${file.name}</h4>
        <p class="text-sm text-gray-500 dark:text-gray-400">${file.size_formatted} · ${file.extension.toUpperCase()}</p>
      </div>
      
      <!-- Actions -->
      <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        ${file.type === 'video' || file.type === 'image' ? `
          <a href="${file.download_url}" target="_blank" class="p-2 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-zinc-700 rounded-lg transition-colors" title="View">
            <i data-lucide="eye" class="w-5 h-5"></i>
          </a>
        ` : ''}
        <a href="${file.download_url}" download class="p-2 text-brand hover:bg-brand/10 rounded-lg transition-colors" title="Download">
          <i data-lucide="download" class="w-5 h-5"></i>
        </a>
        <button onclick="deleteDownload('${file.name}')" class="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors" title="Delete">
          <i data-lucide="trash-2" class="w-5 h-5"></i>
        </button>
      </div>
    </div>
  `;
}

// Delete Download - O(1) API call + O(n) re-render
async function deleteDownload(filename) {
  if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;

  try {
    const response = await fetch(`/api/downloads/${encodeURIComponent(filename)}`, {
      method: 'DELETE'
    });

    if (response.ok) {
      // Remove from local array - O(n)
      downloadedFiles = downloadedFiles.filter(f => f.name !== filename);
      
      if (downloadedFiles.length === 0) {
        document.getElementById('downloads-empty').classList.remove('hidden');
        document.getElementById('downloads-grid').innerHTML = '';
        document.getElementById('downloads-list').innerHTML = '';
      } else {
        renderDownloads();
      }
      
      document.getElementById('downloads-count').textContent = `${downloadedFiles.length} file${downloadedFiles.length !== 1 ? 's' : ''}`;
    } else {
      const data = await response.json();
      alert(data.detail || 'Failed to delete file');
    }
  } catch (error) {
    console.error('Error deleting file:', error);
    alert('Failed to delete file');
  }
}

// Refresh Downloads List
function refreshDownloadsList() {
  loadDownloadsList();
}

// Make functions globally available
window.switchContentTab = switchContentTab;
window.toggleDownloadsView = toggleDownloadsView;
window.refreshDownloadsList = refreshDownloadsList;
window.deleteDownload = deleteDownload;