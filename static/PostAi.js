function toggleLoading(btnId, isLoading, loadingText = 'Processing...', originalText = '', originalIconHtml = '') {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    if (isLoading) {
        if (!btn.dataset.originalText) btn.dataset.originalText = btn.innerText.trim();
        if (!btn.dataset.originalIcon) btn.dataset.originalIcon = btn.querySelector('svg')?.outerHTML || '';
        
        btn.disabled = true;
        btn.classList.add('opacity-75', 'cursor-not-allowed');
        btn.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-current inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            ${loadingText}
        `;
    } else {
        btn.disabled = false;
        btn.classList.remove('opacity-75', 'cursor-not-allowed');
        const icon = originalIconHtml || btn.dataset.originalIcon;
        const text = originalText || btn.dataset.originalText;
        btn.innerHTML = `${icon} ${text}`;
    }
  }

  // --- Helper 2: Generate Image HTML with Loading Spinner ---
  function getImageHtmlWithLoader(url, alt, imgClasses = 'h-full w-full object-cover') {
    if (!url) {
        return `
            <div class="flex items-center justify-center h-full w-full text-slate-300 dark:text-slate-600 bg-slate-100 dark:bg-slate-900">
               <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                  <circle cx="8.5" cy="8.5" r="1.5"></circle>
                  <polyline points="21 15 16 10 5 21"></polyline>
               </svg>
            </div>
        `;
    }

    const cacheBuster = Date.now();
    const imgId = 'lazyimg-' + Math.random().toString(36).substr(2, 9);

    return `
        <div class="relative w-full h-full bg-slate-100 dark:bg-slate-900 flex items-center justify-center overflow-hidden">
            <!-- Spinner -->
            <div class="absolute inset-0 flex items-center justify-center img-loader z-20">
                <svg class="animate-spin h-6 w-6 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            </div>

            <!-- Image (lazy in grid, eager in modal via forced src) -->
            <img 
                id="${imgId}"
                ${url.includes('placeholder') ? '' : `data-src="${url}?t=${cacheBuster}"`}
                src="${url}?t=${cacheBuster}"
                class="${imgClasses} opacity-0 transition-opacity duration-500 z-10"
                alt="${alt}"
                loading="lazy"
                onload="this.classList.remove('opacity-0'); this.closest('div').querySelector('.img-loader')?.remove()"
                onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAyNCIgaGVpZ2h0PSI1NzYiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjEwMjQiIGhlaWdodD0iNTc2IiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtc2l6ZT0iNjQiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIiBmaWxsPSIjOTk5Ij7wn5mD8J+ZiDwvdGV4dD48L3N2Zz4='"
            />
        </div>
    `;
}

  let currentDraftOffset = 0;
  const DRAFT_LIMIT = 4; 
  
  function getGridColsClass(count) {
      if (count >= 5) return 'grid-cols-5';
      if (count === 4) return 'grid-cols-4';
      if (count === 3) return 'grid-cols-3';
      if (count === 2) return 'grid-cols-2';
      // Min 2 columns if drafts exist, otherwise the no-draft message is shown
      return 'grid-cols-2'; 
  }
  
  async function loadDrafts(offset = 0) {
      currentDraftOffset = offset;
      try {
  
          const res = await fetch(`/api/tasks?limit=${DRAFT_LIMIT}&offset=${currentDraftOffset}`);
          const data = await res.json();
          
          const tasks = data.tasks;
          const totalCount = data.total_count;
  
          const grid = document.getElementById('draftsGrid');
          const countSpan = document.getElementById('draftCount');
          const noDrafts = document.getElementById('noDrafts');
          const PaginBtns = document.getElementById('PaginBtns');
          const prevButton = document.getElementById('prevDrafts');
          const nextButton = document.getElementById('nextDrafts');
  
          countSpan.textContent = totalCount;
          
          // --- Handle No Drafts State ---
          if (totalCount === 0) {
              noDrafts.classList.remove('hidden');
              grid.innerHTML = '';
              // Disable both buttons when no drafts exist
              prevButton.setAttribute('disabled', 'disabled');
              nextButton.setAttribute('disabled', 'disabled');
              return;
          }
          noDrafts.classList.add('hidden');
          PaginBtns.classList.remove('hidden');
  
          const newColClass = getGridColsClass(tasks.length);
          
          // Note: Tailwind classes are preserved, assuming no drafts grid needs to be empty/hidden
          grid.className = `grid gap-6 ${newColClass}`; 
  
          // --- Render Drafts (mapping HTML remains the same) ---
          grid.innerHTML = tasks.map(task => `
          <div class="group relative flex flex-col bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 transition-all duration-200 cursor-pointer overflow-hidden"
              onclick="openPostUiModal('${task.task_id}')">
              
              <div class="relative h-48 w-full overflow-hidden">
                  ${getImageHtmlWithLoader(task.media_url, 'Post Preview', 'h-full w-full object-cover transition-transform duration-500 group-hover:scale-105')}
              </div>
              
              <div class="flex flex-1 flex-col justify-between p-5">
                <div>
                   <h3 class="text-sm font-semibold text-slate-900 dark:text-white line-clamp-2 mb-2">
                      ${task.caption_preview || task.title || 'Untitled Draft'}
                   </h3>
                   
                </div>
                
                <div class="flex items-center justify-between mt-4 pt-4 border-t border-slate-100 dark:border-slate-700">
                   <span class="text-xs font-medium text-slate-400">
                      ${new Date(task.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                   </span>
                   <span class="inline-flex items-center text-xs font-medium text-gray-600 dark:text-gray-400 group-hover:underline">
                      Edit
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="ml-1"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                   </span>
                </div>
              </div>
          </div>
          `).join('');
          
          // --- Handle Pagination Buttons (Updated Logic) ---
  
          // Previous Button (Newer Drafts)
          if (data.prev_offset !== null) {
              // Found a previous page, so ENABLE the button
              prevButton.removeAttribute('disabled');
              prevButton.onclick = () => loadDrafts(data.prev_offset);
          } else {
              // At the first page (offset 0), so DISABLE the button
              prevButton.setAttribute('disabled', 'disabled');
          }
  
          // Next Button (Older Drafts)
          if (data.next_offset !== null) {
              // Found a next page, so ENABLE the button
              nextButton.removeAttribute('disabled');
              nextButton.onclick = () => loadDrafts(data.next_offset);
          } else {
              // At the last page, so DISABLE the button
              nextButton.setAttribute('disabled', 'disabled');
          }
  
      } catch (err) {
          console.error('Failed to load drafts:', err);
          // You might want to display an error message here
      }
  }


  document.addEventListener('DOMContentLoaded', () => {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                if (!img.src && img.dataset.src) {
                    img.src = img.dataset.src;
                }
                img.onload = () => {
                    img.classList.remove('opacity-0');
                    const loader = img.closest('div')?.querySelector('.img-loader');
                    if (loader) loader.remove();
                };
                observer.unobserve(img);
            }
        });
    }, { rootMargin: '50px' });

    window.triggerLazyLoad = () => {
        document.querySelectorAll('img[data-src]').forEach(img => {
            if (!img.src.includes('data:')) {
                observer.observe(img);
            }
        });
    };

    // Auto-run after any dynamic content
    new MutationObserver(() => {
        window.triggerLazyLoad();
    }).observe(document.body, { childList: true, subtree: true });

    // Initial run
    window.triggerLazyLoad();
});

  loadDrafts();

  document.getElementById('generateForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const loading = document.getElementById('loading');
    const preview = document.getElementById('preview');
    const genBtnSpan = document.getElementById("genBtnSpan");
    const genBtnBtn = document.getElementById("genBtnBtn");

    const originalBtnText = genBtnSpan.innerText; 
    genBtnSpan.innerText = 'Generating...';
    genBtnBtn.disabled = true;
    genBtnBtn.style.cursor = 'not-allowed'; 

    loading.classList.remove('hidden');
    preview.classList.add('hidden');

    try {
        const res = await fetch('/generate-preview', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
            renderPreview(data);
            preview.classList.remove('hidden');
            loadDrafts();
        } else {
            alert(data.error || 'Generation failed');
        }
    } catch (err) {
        alert('Error: ' + err.message);
    } finally {
     
        loading.classList.add('hidden');
        genBtnSpan.innerText = originalBtnText; 
        genBtnBtn.disabled = false;
        genBtnBtn.style.cursor = 'pointer'; 
        updateCarouselDrf();
    }
});

  function renderPreview(data) {
    document.getElementById('preview').innerHTML = `
      <div class="bg-gray-50 dark:bg-slate-700/50 p-3 border-b border-slate-200 dark:border-slate-700 flex justify-between items-center">
          <h3 class="text-lg font-bold text-gray-700 dark:text-gray-300">Draft Preview</h3>
          <button onclick="document.getElementById('preview').classList.add('hidden')" class="text-slate-400 hover:text-slate-600"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
      </div>
      <div class="p-4 ">
          <div class="prose prose-slate dark:prose-invert max-w-none mb-6">
              <p class="whitespace-pre-wrap text-base leading-relaxed">${data.result.caption}</p>
          </div>
          <div class="flex flex-wrap gap-2 mb-6">
              ${data.result.hashtags.map(tag => 
                  `<span class="inline-flex items-center px-2.5 py-1 rounded-full text-sm font-medium bg-blue-100 text-gray-800 dark:bg-blue-900/50 dark:text-blue-200">${tag}</span>`
              ).join('')}
          </div>
          ${data.result.image_prompt ? `
            <div class="bg-slate-50 dark:bg-slate-900 p-4 rounded-lg border border-slate-200 dark:border-slate-700">
              <span class="text-xs font-bold text-slate-500 uppercase tracking-wide block mb-1">Image Prompt</span>
              <code class="text-xs sm:text-sm font-mono text-slate-700 dark:text-slate-300 block">${data.result.image_prompt}</code>
            </div>` : ''}
          
          <div class="mt-4 flex justify-center">
               <p class="text-sm text-slate-500">Draft saved to library automatically.</p>
          </div>
      </div>
    `;
  }


  async function openPostUiModal(taskId) {
    const res = await fetch(`/tasks/${taskId}`);
    const data = await res.json();
    const content = data.content || {};
    const mediaUrl = data.media_url;
    const initialImagePrompt = content.image_prompt || '';
    
    const modalContent = document.getElementById('modalContent');
    
    const iconSave = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mr-2 inline"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>`;
    const iconRefresh = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mr-2 inline"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>`;
    const iconTrash = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mr-2 inline"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`;
    const iconX = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
    
    modalContent.innerHTML = `
      <div class="flex flex-col h-full">
          <div class="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-850">
              <div class="text-left">
                  <h2 class="text-lg font-bold text-slate-900 dark:text-white">Edit Draft</h2>
                  <p class="text-xs text-slate-500 font-mono">${taskId}</p>
              </div>
                <div class="flex gap-3" >
                    <button id="btn-approve-${taskId}" onclick="approveDraft('${taskId}')" 
                            class="flex items-center justify-center bg-white border border-gray-200 hover:bg-gray-200 text-gray-800 px-4 py-2 rounded-3xl text-sm font-semibold transition-all">
                            Approve Draft
                    </button>
                    <button onclick="closePostUiModal()" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-2 rounded-lg transition-colors">
                        ${iconX}
                    </button>
                </div>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-12 gap-0">
              <div class="lg:col-span-7 p-6 sm:p-8 space-y-6 max-h-[70vh] overflow-y-auto no-scrollbar border-r border-slate-200 dark:border-slate-700">
                  <div class="space-y-1 text-left">
                      <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Post Caption</label>
                      <textarea id="caption" class="w-full p-4 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:ring-2 focus:ring-gray-500 focus:border-transparent transition shadow-sm outline-none" rows="8">${content.caption || ''}</textarea>
                  </div>

                  <div class="space-y-1 text-left">
                      <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Hashtags <span class="text-slate-400 normal-case font-normal">(JSON format)</span></label>
                      <input id="hashtags" class="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-mono text-slate-600 dark:text-slate-300 focus:ring-2 focus:ring-gray-500 focus:border-transparent transition outline-none" 
                             value='${JSON.stringify(content.hashtags || [])}'>
                  </div>

                  <div class="space-y-1 text-left">
                      <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider">Image Prompt</label>
                      <textarea id="image_prompt" class="w-full p-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-mono text-slate-600 dark:text-slate-300 focus:ring-2 focus:ring-gray-500 focus:border-transparent transition outline-none" rows="7">${initialImagePrompt}</textarea>
                  </div>
              </div>

              <div class="lg:col-span-5 bg-slate-50 dark:bg-black/20 p-6 sm:p-8 flex flex-col gap-6">
                  <div id="imagePreview" class="flex-1 min-h-[250px] bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden flex items-center justify-center relative shadow-sm group">
                       ${getImageHtmlWithLoader(mediaUrl, 'Preview', 'w-full h-full object-contain')}
                  </div>

                  <!-- add a small status display and the approve button (inside existing modal template) -->
                <div class="flex flex-col gap-3">
                    <div class="flex items-center justify-between px-2">
                        <div class="text-xs text-slate-500">Status</div>
                        <!-- show current status; id used to update after approval -->
                        <div id="task-status-${taskId}" class="text-xs font-mono text-slate-700 dark:text-slate-300">
                            ${ (data && data.task && data.task.status) ? data.task.status : 'unknown' }
                        </div>
                    </div>

                    <button id="btn-save-${taskId}" onclick="savePostDraft('${taskId}')" 
                            class="flex items-center justify-center w-full bg-gray-800 hover:bg-black text-white px-4 py-3 rounded-xl text-sm font-bold transition-all shadow-md">
                        Save
                    </button>

                    <button id="btn-regen-${taskId}" onclick="saveAndRegenerateImage('${taskId}')" 
                            class="hidden flex items-center justify-center w-full border border-slate-300 dark:border-slate-600 hover:bg-white dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 px-4 py-3 rounded-xl text-sm font-semibold transition-all">
                        ${iconRefresh} Generate Image
                    </button>

                    <div class="h-px bg-slate-200 dark:bg-slate-700 my-1"></div>

                    <button id="btn-del-${taskId}" onclick="deleteDraft('${taskId}')" 
                            class="flex items-center justify-center w-full text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/10 px-4 py-3 rounded-xl text-sm font-semibold transition-all">
                        ${iconTrash} Delete Draft
                    </button>
                </div>

              </div>
          </div>
      </div>
    `;

    const approveBtn = document.getElementById(`btn-approve-${taskId}`);
    const status = data && data.task && data.task.status ? data.task.status : null;
    if (approveBtn) {
        if (status !== 'draft') {
            // hide for non-draft states
            approveBtn.classList.add('hidden');
        } else {
            approveBtn.classList.remove('hidden');
        }
    }

    
    const imgPromptField = document.getElementById('image_prompt');
    const regenBtn = document.getElementById(`btn-regen-${taskId}`);
    
    const updatePostUiBtn = () => {
        if(imgPromptField.value.trim() !== '') {
            regenBtn.classList.remove('hidden');
        } else {
            regenBtn.classList.add('hidden');
        }
    }
    updatePostUiBtn();
    imgPromptField.addEventListener('input', updatePostUiBtn);
    
    document.getElementById('postUiModalOverlay').classList.remove('hidden');
  }

  async function approveDraft(taskId) {
    const approveBtn = document.getElementById(`btn-approve-${taskId}`);
    const statusEl = document.getElementById(`task-status-${taskId}`);

    if (!approveBtn) return;

    // Confirm user action (production: could be a nicer dialog)
    const confirmed = window.confirm("Approve this draft and mark it ready to schedule?");
    if (!confirmed) return;

    // optimistic UI: disable button to prevent double clicks
    approveBtn.disabled = true;
    const previousHtml = approveBtn.innerHTML;
    approveBtn.innerHTML = 'Approving...';

    try {
        const res = await fetch(`/tasks/${taskId}/approve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!res.ok) {
            // try to parse JSON error body
            let errMsg = `${res.status} ${res.statusText}`;
            try {
                const err = await res.json();
                errMsg = err.detail || JSON.stringify(err);
            } catch (_) {}
            // show friendly message
            window.alert(`Failed to approve draft: ${errMsg}`);
            approveBtn.disabled = false;
            approveBtn.innerHTML = previousHtml;
            return;
        }

        const data = await res.json();

        // update status display
        if (statusEl && data && data.task && data.task.status) {
            statusEl.textContent = data.task.status;
        }


        approveBtn.innerHTML = 'Approved';
        approveBtn.disabled = true;

    } catch (err) {
        console.error("approveDraft error:", err);
        window.alert('Network error while approving draft. Please try again.');
        approveBtn.disabled = false;
        approveBtn.innerHTML = previousHtml;
    }
}


  function closePostUiModal() {
    document.getElementById('postUiModalOverlay').classList.add('hidden');
  }

  async function savePostDraft(taskId) { 
    toggleLoading(`btn-save-${taskId}`, true, 'Saving...');
    try {
        await doSave(taskId, false); 
    } finally {
        toggleLoading(`btn-save-${taskId}`, false);
    }
  }

  async function saveAndRegenerateImage(taskId) {
        toggleLoading(`btn-regen-${taskId}`, true, 'Generating...');
        const preview = document.getElementById('imagePreview');
        try {
            const success = await doSave(taskId, true);
            if (success) {
                
                const generateRes = await fetch(`/tasks/${taskId}/generate-image`, { method: 'POST' });
                const generateData = await generateRes.json();
                
                if (generateData.success) { 

                    const initialRes = await fetch(`/tasks/${taskId}`);
                    const initialData = await initialRes.json();
    
                    preview.innerHTML = getImageHtmlWithLoader(initialData.media_url, 'Generated Preview', 'w-full h-full object-contain');
                    window.triggerLazyLoad?.(); 
    

                    const pollInterval = setInterval(async () => {
                        try {
                            const pollRes = await fetch(`/tasks/${taskId}`);
                            const pollData = await pollRes.json(); // <-- pollData is defined here
                            
                           
                            if (pollData.media_url && !pollData.media_url.includes('placeholder')) {
                                clearInterval(pollInterval);
                               
                                preview.innerHTML = getImageHtmlWithLoader(pollData.media_url, 'Generated Preview', 'w-full h-full object-contain');
                                window.triggerLazyLoad?.();
                            }
                        } catch (pollErr) { console.error(pollErr); }
                    }, 2000);
    
                    setTimeout(() => clearInterval(pollInterval), 300000); 
                } else { 
                    preview.innerHTML = `<span class="text-red-500 text-sm">Generation failed</span>`;
                }
            }
        } catch (e) { 
            console.error(e);
        } finally {
            toggleLoading(`btn-regen-${taskId}`, false);
            
        }
    }

  async function doSave(taskId, andRegenerate = false) {
    const caption = document.getElementById('caption').value;
    const hashtagsInput = document.getElementById('hashtags').value;
    const imagePrompt = document.getElementById('image_prompt').value.trim();

    let hashtags = [];
    try { 
        hashtags = JSON.parse(hashtagsInput); 
        if (!Array.isArray(hashtags)) throw 0; 
    } catch { 
        alert('Hashtags must be a JSON array, e.g. ["#tech"]'); 
        return false; 
    }

    if (andRegenerate && !imagePrompt) { 
        alert('Please enter an image prompt.'); 
        return false; 
    }

    const formData = new FormData();
    formData.append('caption', caption);
    formData.append('hashtags', JSON.stringify(hashtags));
    formData.append('image_prompt', imagePrompt);

    try {
        const res = await fetch(`/tasks/${taskId}`, { method: 'PUT', body: formData });
        if (res.ok) {
            if (!andRegenerate) { 
                closePostUiModal(); 
                loadDrafts(); 
            }
            return true;
        }
        alert('Failed to save.');
        return false; 
    } catch (e) {
        alert('Network error.');
        return false;
    }
  }

  async function deleteDraft(taskId) {
    if (confirm('Delete this draft permanently?')) {
        toggleLoading(`btn-del-${taskId}`, true, 'Deleting...');
        try {
            await fetch(`/tasks/${taskId}`, { method: 'DELETE' });
            closePostUiModal();
            loadDrafts();
        } catch (e) {
            toggleLoading(`btn-del-${taskId}`, false);
            alert('Failed to delete.');
        }
    }
  }