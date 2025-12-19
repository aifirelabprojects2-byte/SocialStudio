
let state = {
    limit: 10,     
    nextOffset: null,
    prevOffset: null,
    currentOffset: 0
};



document.addEventListener('DOMContentLoaded', () => {
    fetchData(0);

    els.btnPrev.addEventListener('click', () => {
        if (state.prevOffset !== null) {
            fetchData(state.prevOffset);
        }
    });

    els.btnNext.addEventListener('click', () => {
        if (state.nextOffset !== null) {
            fetchData(state.nextOffset);
        }
    });

});

async function fetchData(offset = 0) {
    setLoading(true);
    try {
        state.currentOffset = offset;

        const res = await fetch(`/api/tasks/approved?limit=${state.limit}&offset=${offset}`);
        if (!res.ok) throw new Error("API Failed");
        
        const data = await res.json();

        state.nextOffset = data.next_offset; 
        state.prevOffset = data.prev_offset;

        if (data.limit) state.limit = data.limit;

        renderTable(data.tasks);
        renderPagination(data);
        
    } catch (err) {
        console.error(err);
        els.tbody.innerHTML = '';
        els.error.classList.remove('hidden');
        els.empty.classList.add('hidden');
    } finally {
        setLoading(false);
    }
}

function renderPagination(data) {
    const total = data.total_count || 0;
    const count = data.tasks ? data.tasks.length : 0;
    
    // Calculate "Showing X - Y"
    const start = count === 0 ? 0 : state.currentOffset + 1;
    const end = state.currentOffset + count;
    
    els.lblStart.textContent = start;
    els.lblEnd.textContent = end;
    els.lblTotal.textContent = total;

    els.btnPrev.disabled = (state.prevOffset === null);
    els.btnNext.disabled = (state.nextOffset === null);
}

function renderTable(tasks) {
    els.tbody.innerHTML = '';
    els.error.classList.add('hidden');

    if (!tasks || tasks.length === 0) {
        els.empty.classList.remove('hidden');
        els.empty.classList.add('flex');
        return;
    }
    
    els.empty.classList.add('hidden');
    els.empty.classList.remove('flex');

    tasks.forEach(t => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-gray-50 transition-colors duration-150 group";
        
        const dateStr = t.created_at ? new Date(t.created_at).toLocaleDateString() : '-';
        
        // Thumbnail Logic
        let mediaHtml = '';
        if(t.has_image && t.media_url) {
            mediaHtml = `<img src="${t.media_url}" class="h-10 w-10 rounded-lg object-cover border border-gray-200 group-hover:border-gray-300">`;
        } else {
            mediaHtml = `<div class="h-10 w-10 rounded bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-400 border border-gray-200">TXT</div>`;
        }
        tr.innerHTML = `
            <td class="whitespace-nowrap py-4 pl-4 pr-3 sm:pl-6">
                <div class="flex items-center">
                    <div class="h-10 w-10 flex-shrink-0">
                        ${mediaHtml}
                    </div>
                    <div class="ml-4">
                        <div class="font-sembold text-gray-900">${escapeHtml(t.title || 'Untitled')}</div>
                        <div class="text-gray-500 text-xs truncate max-w-[200px]">${escapeHtml(t.caption_preview || '')}</div>
                    </div>
                </div>
            </td>
            <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">${dateStr}</td>
            <td class="whitespace-nowrap px-3 py-4 text-sm">
              <span class="text-xs font-medium px-2.5 py-1 rounded-full bg-green-100 dark:bg-green-700 text-green-800 dark:text-green-200">Approved</span>  
            </td>
            <td class="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                
            <button id="viewBtnApr-${t.task_id}" class="text-xs inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-xl hover:shadow-sm" onclick="openDetail('${t.task_id}')">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none"><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5s8.268 2.943 9.542 7c-1.274 4.057-5.065 7-9.542 7S3.732 16.057 2.458 12z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              View
              </button>
          </td>
        `;
        els.tbody.appendChild(tr);
    });
}

function setLoading(bool) {
    if(bool) {
        skeletonDraft.classList.remove('hidden')
        els.tbody.classList.add('hidden'); 
    } else {
        skeletonDraft.classList.add('hidden')
        els.tbody.classList.remove('hidden');
    }
}




const els = {
tbody: document.getElementById('tableBody'),
skeletonDraft: document.getElementById('skeletonDraft'),
empty: document.getElementById('emptyState'),
error: document.getElementById('errorState'),
lblStart: document.getElementById('lblStart'),
lblEnd: document.getElementById('lblEnd'),
lblTotal: document.getElementById('lblTotal'),
btnPrev: document.getElementById('btnPrev'),
btnNext: document.getElementById('btnNext'),
overlaymodal: document.getElementById('modalOverlay'),
title: document.getElementById('modalTitle'),
content: document.getElementById('modalContentText'),
hashtags: document.getElementById('modalHashtags'),
time: document.getElementById('modalTime'),
img: document.getElementById('modalImg'),
noImg: document.getElementById('modalNoImg'),
platforms: document.getElementById('platformsList'),
scheduleSection: document.getElementById('schedulingSection'),
scheduleBtn: document.getElementById('scheduleBtn'),
scheduledInput: document.getElementById('scheduledAtInput'),
notes: document.getElementById('notesInput'),
closeBtn: document.getElementById('closeModalBtn'),
inswarn: document.getElementById('inswarn')
};

async function openDetail(taskId) {
    toggleLoading(`viewBtnApr-${taskId}`, true, 'Opening');
    
try {
    const res = await fetch(`/api/tasks/approved/${taskId}`);
    if (!res.ok) throw new Error("Err");
    const d = await res.json();
    const task_id = d.task_id;
    const gc = d.generated_content || {};

    // Populate basic details
    els.title.textContent = d.title || "Task Details";
    els.content.textContent = gc.caption || '';
    
    const tags = gc.hashtags || [];
    els.hashtags.textContent = tags.map(t => `#${t}`).join(' ');
    els.time.textContent = gc.suggested_posting_time || "Not scheduled";

    // Handle Image
    if (d.preview_image) {
        els.img.src = d.preview_image;
        els.img.style.display = 'block';
        els.noImg.classList.add('hidden');
    } else {
        els.img.style.display = 'none';
        els.noImg.classList.remove('hidden');
        els.noImg.style.display = 'flex'; 
    }

    // Fetch available platforms
    const platformsRes = await fetch('/api/active/platforms');
    if (!platformsRes.ok) {
        console.error('Failed to fetch platforms');
        populatePlatforms([
            { platform_id: 'aaa', name: 'No Platform Configured' },
            { platform_id: 'threads-platform-uuid', name: 'Threads' },
            { platform_id: 'facebook-platform-uuid', name: 'Facebook' }
        ]);
    } else {
        const platformsData = await platformsRes.json();
        console.log(platformsData);
        populatePlatforms(platformsData || []);
    }
    
    const now = new Date();
    now.setHours(now.getHours() + 1);

    const offset = now.getTimezoneOffset() * 60000;
    const localISOTime = (new Date(now - offset)).toISOString().slice(0, 16);
    
    els.scheduledInput.value = localISOTime;

    const minTime = (new Date(Date.now() - offset)).toISOString().slice(0, 16);
    els.scheduledInput.min = minTime;

    els.scheduleSection.classList.remove('hidden');
    els.scheduleBtn.classList.remove('hidden');

    const newBtn = els.scheduleBtn.cloneNode(true);
    els.scheduleBtn.parentNode.replaceChild(newBtn, els.scheduleBtn);
    els.scheduleBtn = newBtn; 
    
    els.scheduleBtn.onclick = () => handleSchedule(task_id);

    els.overlaymodal.classList.remove('hidden');
} catch (e) {
    console.error(e);
    alert("Could not load details");
    toggleLoading(`viewBtnApr-${taskId}`, true, 'Opening');
}
finally{
    toggleLoading(`viewBtnApr-${taskId}`, false);
}
}

function populatePlatforms(platforms) {
    els.platforms.innerHTML = ''; // Clear previous content

    if (platforms.length === 0) {
        els.platforms.classList.remove(
            "grid",
            "grid-cols-1",
            "sm:grid-cols-2",
            "gap-3"
          );
        els.inswarn.classList.add('hidden');
          
        els.platforms.classList.add('flex');
        const emptyMessage = document.createElement('div');
        emptyMessage.innerHTML = `
            <div class="max-w-md mx-auto rounded-xl border px-7 py-4 border-gray-100">
                <div class="flex justify-center items-center gap-2">
                    <svg class="h-6 w-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <h3 class="text-lg font-medium text-gray-900">
                        No Connected Platforms
                    </h3>
                </div>

                <p class="mt-2 text-sm text-gray-600 leading-relaxed">
                    There are currently no social media platforms connected to your account.
                    To begin publishing or managing content, please connect a platform from
                    <span class="font-medium text-gray-700">Settings → Setup</span>.
                </p>
            </div>
        `;

        els.platforms.appendChild(emptyMessage);
        return;
    }

    // Normal case: render platform toggles
    platforms.forEach(platform => {
        const platformId = platform.platform_id;
        const div = document.createElement('div');

        div.className = 'relative flex items-center justify-between p-3 bg-white rounded-xl border border-gray-100 hover:border-gray-500 transition-all cursor-pointer';

        div.innerHTML = `
            <label for="platform-toggle-${platformId}" class="text-sm font-medium text-gray-900 select-none cursor-pointer">
                ${platform.name}
            </label>
            
            <input type="checkbox" id="platform-toggle-${platformId}" value="${platformId}" 
                   class="sr-only peer"> 
            
            <div class="relative w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border after:border-gray-300 after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gray-800"></div>
            
            <label for="platform-toggle-${platformId}" class="absolute inset-0 cursor-pointer"></label>
        `;
        
        els.platforms.appendChild(div);
    });
}
async function handleSchedule(taskId) {
const platformCheckboxes = document.querySelectorAll('#platformsList input[type="checkbox"]:checked');
const platformIds = Array.from(platformCheckboxes).map(cb => cb.value);

if (platformIds.length === 0) {
    ShowNoti('info', 'Please select at least one platform');
    return;
}

const scheduledAtStr = els.scheduledInput.value;
if (!scheduledAtStr) {
    ShowNoti('info', 'Please select a scheduled date and time')
    return;
}

// Convert local input to ISO string for backend
// Assuming backend expects UTC or explicit offset
const scheduledAt = new Date(scheduledAtStr).toISOString();

const notes = els.notes.value.trim();

const requestBody = {
    task_id: taskId,
    platform_ids: platformIds,
    scheduled_at: scheduledAt,
    notes: notes || undefined
};

// UI: Show loading state
const originalBtnText = els.scheduleBtn.innerText;
els.scheduleBtn.innerText = 'Scheduling...';
els.scheduleBtn.disabled = true;

try {
    const res = await fetch('/schedule-task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to schedule task');
    }

    const data = await res.json();
    // Modern approach: Toast or nice alert (sticking to alert per request)
    alert(`Task scheduled successfully!`);
    
    closeModal();
    // location.reload(); // Optional: reload to update UI
} catch (e) {
    console.error(e);
    alert(`Error: ${e.message}`);
} finally {
    els.scheduleBtn.innerText = originalBtnText;
    els.scheduleBtn.disabled = false;
}
}

function closeModal() {
els.overlaymodal.classList.add('hidden');

els.scheduleSection.classList.add('hidden');
els.scheduleBtn.classList.add('hidden');
els.platforms.innerHTML = '';
els.notes.value = '';
els.scheduledInput.value = '';
els.img.src = '';
}

els.closeBtn.onclick = closeModal;

function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
