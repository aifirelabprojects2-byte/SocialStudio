function toggleLoading(btnId, isLoading, loadingText = 'Processing...') {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    const preserveHtml = btn.dataset.preserveHtml === "true";

    if (isLoading) {
        if (!btn.dataset.originalHtml && preserveHtml) {
            btn.dataset.originalHtml = btn.innerHTML;
        }
        if (!btn.dataset.originalText && !preserveHtml) {
            btn.dataset.originalText = btn.innerText.trim();
            btn.dataset.originalIcon = btn.querySelector('svg')?.outerHTML || '';
        }

        btn.disabled = true;
        btn.classList.add('opacity-75', 'cursor-not-allowed');

        btn.innerHTML = `
            <svg class="animate-spin h-4 w-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
            <span class="text-xs">${loadingText}</span>
        `;
    } else {
        btn.disabled = false;
        btn.classList.remove('opacity-75', 'cursor-not-allowed');

        if (preserveHtml && btn.dataset.originalHtml) {
            btn.innerHTML = btn.dataset.originalHtml;
        } else {
            const text = btn.dataset.originalText || '';
            const icon = btn.dataset.originalIcon || '';
            btn.innerHTML = `${text} ${icon}`;
        }
    }
}


  function getImageHtmlWithLoader(url, alt, imgClasses = 'h-full w-full object-cover') {
    if (!url) {
        return `
            <div class="flex items-center justify-center h-full w-full text-slate-300 dark:text-slate-600 bg-slate-100 dark:bg-zinc-900">
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
        <div class="relative w-full h-full bg-slate-100 dark:bg-zinc-900 flex items-center justify-center overflow-hidden">
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


  
  function getGridColsClass(count) {
      if (count >= 5) return 'grid-cols-5';
      if (count === 4) return 'grid-cols-4';
      if (count === 3) return 'grid-cols-3';
      if (count === 2) return 'grid-cols-2';
      // Min 2 columns if drafts exist, otherwise the no-draft message is shown
      return 'grid-cols-2'; 
  }
  
  let currentDraftOffset = 0;
  const DRAFT_LIMIT = 4; 
  
  async function loadDrafts(offset = 0) {
       const grid = document.getElementById('draftsGrid');
       noDrafts.classList.add('hidden');
       grid.className = `grid gap-3 sm:gap-4 lg:gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`; 
       grid.innerHTML = "";
       const loadingCard = (i) => `
                            <div class="group relative flex flex-col bg-white dark:bg-zinc-800 rounded-2xl border border-slate-200 dark:border-slate-700 overflow-hidden shadow-sm hover:shadow-lg transition-shadow duration-300 animate-pulse">
                                <div class="relative h-48 sm:h-56 lg:h-64 w-full bg-gray-200 dark:bg-zinc-700 skeletonPlatform-loader"></div>
                                <div class="flex flex-1 flex-col justify-between p-4 sm:p-5 lg:p-6">
                                    <div>
                                        <div class="h-4 sm:h-5 bg-gray-200 dark:bg-zinc-700 rounded-md w-11/12 mb-2 sm:mb-3 skeletonPlatform-loader"></div>
                                        <div class="h-4 sm:h-5 bg-gray-200 dark:bg-zinc-700 rounded-md w-4/6 skeletonPlatform-loader"></div>
                                    </div>
                                    <div class="flex items-center justify-between mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-slate-100 dark:border-slate-700">
                                        <div class="h-3 sm:h-4 bg-gray-200 dark:bg-zinc-700 rounded w-16 sm:w-20 skeletonPlatform-loader"></div>
                                        <div class="flex items-center gap-1.5">
                                            <div class="h-8 sm:h-9 w-16 sm:w-20 bg-gray-200 dark:bg-zinc-700 rounded-xl skeletonPlatform-loader"></div>
                                        </div>
                                    </div>
                                </div>
                            </div>`;
       grid.innerHTML = Array(4).fill().map(loadingCard).join('');
      
        currentDraftOffset = offset;
      try {
  
          const res = await fetch(`/api/tasks?limit=${DRAFT_LIMIT}&offset=${currentDraftOffset}`);
          const data = await res.json();
          
          const tasks = data.tasks;
          const totalCount = data.total_count;
  
          
          
          const countSpan = document.getElementById('draftCount');
          const noDrafts = document.getElementById('noDrafts');
          const PaginBtns = document.getElementById('PaginBtns');
          const prevButton = document.getElementById('prevDrafts');
          const nextButton = document.getElementById('nextDrafts');
  
          countSpan.textContent = `${totalCount} Drafts`;
          if (totalCount === 0) {
              noDrafts.classList.remove('hidden');
              grid.innerHTML = '';
              prevButton.setAttribute('disabled', 'disabled');
              nextButton.setAttribute('disabled', 'disabled');
              return;
          }
          noDrafts.classList.add('hidden');
          PaginBtns.classList.remove('hidden');

          grid.className = `grid gap-3 sm:gap-4 lg:gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`; 

          grid.innerHTML = tasks.map(task => `
            <div class="group relative flex flex-col bg-white dark:bg-zinc-800 rounded-2xl border border-slate-200 dark:border-slate-700  duration-300 cursor-pointer overflow-hidden shadow-sm hover:shadow-xl"
                 onclick="openPostUiModalGfr('${task.task_id}')">
                
                <div class="relative h-48 sm:h-56 lg:h-64 w-full overflow-hidden bg-slate-100 dark:bg-zinc-700">
                    ${getImageHtmlWithLoader(task.media_url, 'Post Preview', 'h-full w-full object-cover transition-transform duration-500 group-hover:scale-105')}
                </div>
                
                <div class="flex flex-1 flex-col justify-between p-4 sm:p-5 lg:p-6">
                    <div>
                        <h3 class="text-sm sm:text-base lg:text-lg font-semibold text-slate-900 dark:text-white line-clamp-2 mb-2">
                            ${task.caption_preview || task.title || 'Untitled Draft'}
                        </h3>
                    </div>
                    
                    <div class="flex items-center justify-between mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-slate-100 dark:border-slate-700">
                        <span class="text-xs sm:text-sm font-medium text-slate-500 dark:text-slate-400">
                            ${new Date(task.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        </span>
                        <button id="editBtnDrf-${task.task_id}" 
                                class="text-xs sm:text-sm font-medium text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-zinc-700 hover:bg-slate-200 dark:hover:bg-slate-600 px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl border border-slate-300 dark:border-slate-600  duration-200 inline-flex items-center gap-2 hover:shadow-md">
                                Edit
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-pencil-line-icon lucide-pencil-line"><path d="M13 21h8"/><path d="m15 5 4 4"/><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/></svg>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
          

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

    const numDrafts = parseInt(formData.get('num_drafts')) || 1;
    const originalBtnText = genBtnSpan.innerText; 
    genBtnSpan.innerText = `Generating ${numDrafts} draft${numDrafts > 1 ? 's' : ''}...`;
    genBtnBtn.disabled = true;
    genBtnBtn.style.cursor = 'not-allowed'; 

    loading.classList.remove('hidden');
    preview.classList.add('hidden');
    loading.innerHTML = `
        <div class="inline-flex items-center px-4 py-2 font-semibold leading-6 text-gray-600 transition ease-in-out duration-150 cursor-not-allowed">
            <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-gray-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Crafting your ${numDrafts > 1 ? 'posts' : 'post'}...
        </div>
    `;

    try {
        const res = await fetch('/generate-preview', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success && data.drafts && data.drafts.length > 0) {
            if (numDrafts === 1) {
                renderPreview(data.drafts[0]);
            } else {
                renderMultiplePreviews(data);
            }
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
    }
});

  function renderPreview(data) {
    document.getElementById('preview').innerHTML = `
      <div class="bg-gray-50 dark:bg-zinc-700/50 p-3 border-b border-slate-200 dark:border-slate-700 flex justify-between items-center">
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
            <div class="bg-slate-50 dark:bg-zinc-900 p-4 rounded-lg border border-slate-200 dark:border-slate-700">
              <span class="text-xs font-bold text-slate-500 uppercase tracking-wide block mb-1">Image Prompt</span>
              <code class="text-xs sm:text-sm font-mono text-slate-700 dark:text-slate-300 block">${data.result.image_prompt}</code>
            </div>` : ''}
          
          <div class="mt-4 flex justify-center">
               <p class="text-sm text-slate-500">Draft saved to library automatically.</p>
          </div>
      </div>
    `;
  }

  function renderMultiplePreviews(data) {
    const num = data.drafts.length;
    const previews = data.drafts.slice(0, 4).map(d => `
      <div class="bg-white dark:bg-zinc-900 p-4 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
        <div class="prose prose-sm prose-slate dark:prose-invert max-w-none mb-3">
          <p class="line-clamp-3">${d.result.caption}</p>
        </div>
        <div class="flex flex-wrap gap-1 mb-2">
          ${d.result.hashtags.slice(0, 3).map(tag => 
            `<span class="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-200">${tag}</span>`
          ).join('')}
        </div>
        ${d.generate_image && d.result.image_prompt ? `
          <div class="text-xs text-slate-500 italic mt-2">${d.result.image_prompt.substring(0, 80)}...</div>
        ` : ''}
      </div>
    `).join('');

    document.getElementById('preview').innerHTML = `
      <div class="bg-gray-50 dark:bg-zinc-900/50 p-3 border-b border-slate-200 dark:border-slate-700 flex justify-between items-center">
          <h3 class="text-lg font-bold text-gray-700 dark:text-gray-300">Generated ${num} Drafts</h3>
          <button onclick="document.getElementById('preview').classList.add('hidden')" class="text-slate-400 hover:text-slate-600"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
      </div>
      <div class="p-4">
        <p class="text-sm text-slate-600 dark:text-slate-400 mb-4">Check your library below for all variations. Here's a quick preview of the first few:</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4 mb-4">
          ${previews}
        </div>
        ${num > 4 ? `<p class="text-center text-sm text-slate-500">And ${num - 4} more in your library...</p>` : ''}
        <div class="mt-4 flex justify-center">
          <p class="text-sm text-slate-500">Drafts saved automatically.</p>
        </div>
      </div>
    `;
  }


  const modalCacheDfd = new WeakMap();

  async function openPostUiModalGfr(taskId) {
    const modalDfd = document.getElementById('postUiModalOverlayGfr');
    if (!modalDfd) return;
  
    // Prevent double-opening on fast clicks
    if (modalDfd.dataset.loading === 'true') return;
    modalDfd.dataset.loading = 'true';
  
    toggleLoading(`editBtnDrf-${taskId}`, true, 'Opening...');
  
    try {
      const res = await fetch(`/tasks/${taskId}`);
      if (!res.ok) throw new Error('Network error');
      const data = await res.json();
  
      const content = data.content || {};
      const mediaUrl = data.media_url;
      const status = data.task?.status || 'unknown';
  
      // === CACHE ALL DOM ELEMENTS ONCE (Gfr IDs, Dfd cache) ===
      let elsDfd = modalCacheDfd.get(modalDfd);
      if (!elsDfd) {
        elsDfd = {
          taskIdEl:      document.getElementById('modalTaskIdGfr'),
          caption:       document.getElementById('captionGfr'),
          hashtags:      document.getElementById('hashtagsGfr'),
          imagePrompt:   document.getElementById('imagePromptGfr'),
          taskStatus:    document.getElementById('taskStatusGfr'),
          imagePreview:  document.getElementById('imagePreviewGfr'),
          approveBtn:    document.getElementById('btnApproveGfr'),
          saveBtn:       document.getElementById('btnSaveGfr'),
          regenBtn:      document.getElementById('btnRegenGfr'),
          deleteBtn:     document.getElementById('btnDeleteGfr'),
        };
        modalCacheDfd.set(modalDfd, elsDfd);
      }
  
      elsDfd.taskIdEl.textContent = taskId;
  
      elsDfd.caption.value = content.caption || '';
      
      elsDfd.hashtags.value = JSON.stringify(content.hashtags || []);
  
      elsDfd.imagePrompt.value = content.image_prompt || '';
      elsDfd.taskStatus.textContent = status;
  
      elsDfd.imagePreview.innerHTML = getImageHtmlWithLoader(
        mediaUrl,
        'Preview',
        'w-full h-full object-cover'
      );
  
      elsDfd.approveBtn.classList.toggle('hidden', status !== 'draft');
  
      const rewireBtnDfd = (btn, handler) => {
        const newBtn = btn.cloneNode(true);
        newBtn.onclick = () => handler(taskId);
        btn.parentNode.replaceChild(newBtn, btn);
        return newBtn;
      };
  
      elsDfd.approveBtn = rewireBtnDfd(elsDfd.approveBtn, approveDraft);
      elsDfd.saveBtn    = rewireBtnDfd(elsDfd.saveBtn,    savePostDraft);
      elsDfd.regenBtn   = rewireBtnDfd(elsDfd.regenBtn,   saveAndRegenerateImage);
      elsDfd.deleteBtn  = rewireBtnDfd(elsDfd.deleteBtn,  deleteDraft);
  
  
      const updateRegenVisibilityDfd = () => {
        elsDfd.regenBtn.classList.toggle('hidden', elsDfd.imagePrompt.value.trim() === '');
      };
  
      elsDfd.imagePrompt.oninput = null;
      elsDfd.imagePrompt.addEventListener('input', updateRegenVisibilityDfd);
      updateRegenVisibilityDfd(); 
  
  
      modalDfd.classList.remove('hidden');
  
    } catch (err) {
      console.error('openPostUiModalGfr error:', err);
      alert('Failed to load post. Please try again.');
    } finally {
      toggleLoading(`editBtnDrf-${taskId}`, false);
      modalDfd.dataset.loading = 'false';
    }
}

function closePostUiModalGfr() {
    document.getElementById('postUiModalOverlayGfr').classList.add('hidden');
}


async function approveDraft(taskId) {
    const approveBtn = document.getElementById(`btnApproveGfr`);
    const statusEl = document.getElementById(`taskStatusGfr`);

    if (!approveBtn) return;

    const confirmed = await askUser(
        "Approve Draft?", 
        "This will mark the content as ready and move it to your approved queue for scheduling."
    );

    if (!confirmed) return;



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
           

            let errMsg = `${res.status} ${res.statusText}`;
            try {
                const err = await res.json();
                errMsg = err.detail || JSON.stringify(err);
            } catch (_) {}
            ShowNoti('error', 'Failed to approve draft');
            approveBtn.disabled = false;
            approveBtn.innerHTML = previousHtml;
            return;
        }

        const data = await res.json();

        // update status display
        if (statusEl && data && data.task && data.task.status) {
            statusEl.textContent = data.task.status;
        }

        ShowNoti('success', 'Draft Approved');
        approveBtn.innerHTML = 'Approved';
        approveBtn.disabled = true;

    } catch (err) {
        ShowNoti('error', 'Failed to approve draft');
        approveBtn.disabled = false;
        approveBtn.innerHTML = previousHtml;
    }
    
}


  function closePostUiModal() {
    document.getElementById('postUiModalOverlayGfr').classList.add('hidden');
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
        toggleLoading(`btnRegenGfr`, true, 'Generating...');
        const preview = document.getElementById('imagePreviewGfr');
        try {
            const success = await doSave(taskId, true);
            if (success) {
                const formData = new FormData();
                formData.append('model', document.getElementById('geminiModelSelect')?.value || 'gemini-2.5-flash-image');  // Assume you add <select id="geminiModelSelect">
                formData.append('watermark_position', document.getElementById('watermarkPos')?.value || null);  // Assume <select id="watermarkPos">
                
                const generateRes = await fetch(`/tasks/${taskId}/generate-image`, { method: 'POST' ,body: formData });
                const generateData = await generateRes.json();
                
                if (generateData.success) { 
                    ShowNoti('success', 'Image Generated');
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
                    ShowNoti('error', 'Generation failed');
                    preview.innerHTML = `<span class="text-red-500 text-sm">Generation failed</span>`;
                }
            }
        } catch (e) { 
            console.error(e);
            toggleLoading(`btnRegenGfr`, false);
        } finally {
            
            toggleLoading(`btnRegenGfr`, false);
            
        }
    }

  async function doSave(taskId, andRegenerate = false) {
    const caption = document.getElementById('captionGfr').value;
    const hashtagsInput = document.getElementById('hashtagsGfr').value;
    const imagePrompt = document.getElementById('imagePromptGfr').value.trim();

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
    toggleLoading(`btnSaveGfr`, true, 'Saving...');
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
    finally{
        toggleLoading(`btnSaveGfr`, false);
    }
  }

  async function deleteDraft(taskId) {
    // 1. Call the global confirmation instead of the native alert
    const confirmed = await askUser(
        'Delete this draft?', 
        'This will permanently remove the content. This action cannot be undone.'
    );

    // 2. Proceed only if user confirmed (true)
    if (confirmed) {
        toggleLoading(`btnDeleteGfr`, true, 'Deleting...');
        
        try {
            const response = await fetch(`/tasks/${taskId}`, { method: 'DELETE' });
            
            if (!response.ok) throw new Error('Delete failed');

            closePostUiModal();
            loadDrafts();
            ShowNoti('success', 'Draft deleted successfully');
            
        } catch (e) {
            console.error(e);
            ShowNoti('error', 'Failed to delete the draft');
        } finally {
            toggleLoading(`btnDeleteGfr`, false);
        }
    }
}


const imgToggle = document.getElementById('imgToggle');
const imageStyleContainer = document.getElementById('imageStyleContainer');

function updateImageStyleVisibility() {
    if (imgToggle.checked) {
        imageStyleContainer.classList.remove('hidden');
        imageStyleContainer.classList.add('flex');
    } else {
        imageStyleContainer.classList.add('hidden');
        imageStyleContainer.classList.remove('flex');
    }
}
updateImageStyleVisibility();
imgToggle.addEventListener('change', updateImageStyleVisibility);
