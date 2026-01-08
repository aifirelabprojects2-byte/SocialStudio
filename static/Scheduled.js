const TASKS_ENDPOINT = `/api/tasks-scheduled`;
const TASK_DETAIL_ENDPOINT = '/view/tasks-scheduled';

// State
let currentShdOffset = 0;
let currentShdLimit = 20;
let currentStatus = '';
let totalTasks = 0;
let tasksData = [];

// Utilities
function formatDate(dateStr) {
    if(!dateStr) return 'N/A';
    const d = new Date(dateStr);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

function getStatusBadgeClass(status) {
    const s = (status || '').toLowerCase();
    if (s === 'posted' || s === 'published') return 'bg-green-100 text-green-800 border-green-200';
    if (s === 'failed' || s === 'error') return 'bg-red-100 text-red-800 border-red-200';
    if (s === 'scheduled') return 'bg-blue-100 text-blue-800 border-blue-200';
    if (s === 'cancelled') return 'bg-gray-100 text-gray-800 border-gray-200';
    return 'bg-neutral-100 text-neutral-600 border-neutral-200';
}

function renderHashtags(hashtags) {
    if (!hashtags || hashtags.length === 0) return '<span class="text-neutral-400 italic">None</span>';
    return hashtags.slice(0, 5).map(h => `<span class="inline-block bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded-full mr-1 mb-1">#${h}</span>`).join('') + (hashtags.length > 5 ? ' <span class="text-xs text-neutral-400">+${hashtags.length - 5}</span>' : '');
}

// --- Render Functions ---

function renderTaskRowShd(task, index) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-neutral-50 transition-all duration-200 group';
    
    const badgeClass = getStatusBadgeClass(task.status);

    row.innerHTML = `
        <td class="sched-task-title-${index}Shd px-6 py-5 whitespace-nowrap">
            <div class="text-sm font-semibold text-neutral-900">${task.title || '<span class="italic text-neutral-400">Untitled</span>'}</div>
            <div class="text-xs text-neutral-400 font-mono mt-1">ID: ${task.task_id.substring(0,8)}...</div>
        </td>
        <td class="sched-task-status-${index}Shd px-6 py-5 whitespace-nowrap">
            <span class="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full border ${badgeClass}">
                ${task.status}
            </span>
        </td>
        <td class="sched-task-created-${index}Shd px-6 py-5 whitespace-nowrap text-sm text-neutral-500">
            ${formatDate(task.created_at)}
        </td>
        <td class="sched-task-scheduled-${index}Shd px-6 py-5 whitespace-nowrap text-sm text-neutral-600">
            <div class="flex items-center">
                <svg class="mr-2 h-4 w-4 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                ${task.scheduled_at ? formatDate(task.scheduled_at) : 'N/A'}
            </div>
        </td>
        <td class="sched-task-actions-${index}Shd px-6 py-5 whitespace-nowrap text-right text-sm font-semibold">
            <button class="sched-task-view-btn-${index}Shd text-gray-600 hover:text-gray-700 bg-gray-50 hover:bg-gray-100 px-4 py-2 rounded-xl border  border-gray-200 transition-all duration-200 inline-flex items-center  hover:shadow-medium" onclick="viewTaskShd('${task.task_id}')">
                <svg class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                View
                <div id="btn-spinner-${index}Shd" class="hidden ml-2 animate-spin h-3 w-3 border-2 border-gray-600 border-t-transparent rounded-full"></div>
            </button>
        </td>
    `;
    return row;
}

function renderPaginationInfoShd() {
    const start = currentShdOffset + 1;
    const end = Math.min(currentShdOffset + currentShdLimit, totalTasks);
    const totalStr = totalTasks > 0 ? totalTasks : 0;
    const startStr = totalTasks > 0 ? start : 0;
    const endStr = totalTasks > 0 ? end : 0;
    
    document.getElementById('pageInfoShd').innerHTML = `
        Showing <span class="font-semibold text-neutral-900">${startStr}</span> to <span class="font-semibold text-neutral-900">${endStr}</span> of <span class="font-semibold text-neutral-900">${totalStr}</span> results
    `;
}

function updatePaginationButtonsShd() {
    const prevPageShd = document.getElementById('prevPageShd');
    const nextPageShd = document.getElementById('nextPageShd');
    
    prevPageShd.disabled = currentShdOffset === 0;
    nextPageShd.disabled = currentShdOffset + currentShdLimit >= totalTasks;
}

// --- Fetch Logic ---

async function fetchTasksShd(status = '', limit = 20, offset = 0) {
    const tableLoading = document.getElementById('tableLoadingShd');
    const tasksTableShd = document.getElementById('tasksTableShd');
    const tableBodyShd = document.getElementById('tasksTableBodyShd');
    const noTasks = document.getElementById('noTasksShd');

    tableLoading.classList.remove('hidden');
    tasksTableShd.classList.add('hidden');
    noTasks.classList.add('hidden');

    try {
        const params = new URLSearchParams();
        if (status) params.append('status', status);
        params.append('limit', limit.toString());
        params.append('offset', offset.toString());

        const response = await fetch(`${TASKS_ENDPOINT}?${params}`);
        if (!response.ok) throw new Error('Failed to fetch tasks');
        const data = await response.json();

        tasksData = data.tasks;
        totalTasks = data.total;
        currentShdLimit = data.limit;
        currentShdOffset = data.offset;

        tableBodyShd.innerHTML = '';
        if (data.tasks.length === 0) {
            noTasks.classList.remove('hidden');
        } else {
            data.tasks.forEach((task, index) => {
                tableBodyShd.appendChild(renderTaskRowShd(task, index));
            });
            tasksTableShd.classList.remove('hidden');
        }

        renderPaginationInfoShd();
        updatePaginationButtonsShd();
    } catch (error) {
        console.error('Error fetching tasks:', error);
        noTasks.innerHTML = `
            <div class="text-red-500 flex flex-col items-center">
                <svg class="h-10 w-10 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                <p class="font-semibold text-lg">Connection Error</p>
                <p class="text-sm text-neutral-400 mt-1">Could not retrieve tasks from server.</p>
            </div>
        `;
        noTasks.classList.remove('hidden');
    } finally {
        tableLoading.classList.add('hidden');
    }
}

async function viewTaskShd(taskId) {
    document.getElementById('detailIdDisplayShd').textContent = "-----";
    let statusHeader = document.getElementById('detailStatusHeaderShd');
        statusHeader.textContent = "loading";
        statusHeader.className = `ml-2 inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border ${getStatusBadgeClass("loading")}`;

    const modalShd = document.getElementById('taskDetailsModalShd');
    const modalLoading = document.getElementById('modalLoadingShd');
    const modalContentShd = document.getElementById('modalContentShd');
    
    // Find button that triggered this to show spinner
    const btn = event.target.closest('button');
    const btnSpinner = btn ? btn.querySelector('div[id^="btn-spinner"]') : null;

    if(btn) {
        btn.disabled = true;
        if(btnSpinner) btnSpinner.classList.remove('hidden');
    }

    modalLoading.classList.remove('hidden');
    modalContentShd.classList.add('hidden');
    modalShd.classList.remove('hidden');
    document.body.style.overflow = 'hidden'; 

    try {
        const response = await fetch(`${TASK_DETAIL_ENDPOINT}/${taskId}`);
        if (!response.ok) throw new Error('Failed to fetch task details');
        const data = await response.json();

        // HEADER
        document.getElementById('detailIdDisplayShd').textContent = taskId;
        let statusHeader = document.getElementById('detailStatusHeaderShd');
        statusHeader.textContent = data.task.status;
        statusHeader.className = `ml-2 inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border ${getStatusBadgeClass(data.task.status)}`;

        // SECTION 1: OVERVIEW
        document.getElementById('detailTitleShd').textContent = data.task.title || 'Untitled Task';
        document.getElementById('detailCreatedAtShd').textContent = 'Created ' + formatDate(data.task.created_at);
        document.getElementById('detailUpdatedAtShd').textContent = formatDate(data.task.updated_at);
        document.getElementById('detailScheduledAtShd').textContent = data.task.scheduled_at ? formatDate(data.task.scheduled_at) : 'Not scheduled';
        document.getElementById('detailNotesShd').textContent = data.task.notes || 'No additional notes provided.';
        const captionEl = document.getElementById('captionWithHash');
        const copyBtn = document.getElementById('copyCaptionBtn');
        const copyBtnText = document.getElementById('copyBtnText');
        const copyIcon = document.getElementById('copyIcon');

        if (data.caption_with_hashtags && data.caption_with_hashtags.trim()) {
            const captionText = data.caption_with_hashtags.trim();
            captionEl.textContent = captionText;
        
            const copyIcon = document.getElementById('copyIcon');
            const defaultIconPath = copyIcon.innerHTML; // Save original
        
            copyBtn.onclick = async () => {
                try {
                    await navigator.clipboard.writeText(captionText);
        
                    // Switch to checkmark
                    copyIcon.innerHTML = `
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                              d="M5 13l4 4L19 7" fill="none" stroke="currentColor"/>
                    `;
        
                    // Optional: add a little "success" pulse
                    copyBtn.classList.add('text-green-600');
        
                    setTimeout(() => {
                        copyIcon.innerHTML = defaultIconPath; // Restore original copy icon
                        copyBtn.classList.remove('text-green-600');
                    }, 2000);
        
                } catch (err) {
                    // Optional: brief red flash on fail
                    copyBtn.classList.add('text-red-600');
                    setTimeout(() => copyBtn.classList.remove('text-red-600'), 2000);
                }
            };
        } else {
            captionEl.textContent = 'No caption provided.';
            copyBtn.disabled = true;
            copyBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }

        // === Image Download Button (Actually Downloads!) ===
        const imgBtn = document.getElementById('ImgDwnBtn');
        const downloadText = document.getElementById('downloadBtnText');

        if (data.image_url && data.image_url.trim()) {
            const imageUrl = data.image_url.trim();

            imgBtn.onclick = async (e) => {
                e.preventDefault();
                try {
                    const response = await fetch(imageUrl);
                    if (!response.ok) throw new Error('Image fetch failed');

                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);

                    const a = document.createElement('a');
                    a.href = url;
                    a.download = imageUrl.split('/').pop().split('?')[0].split('#')[0] || 'image.jpg';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);

                    // Optional: visual feedback
                    downloadBtnText.textContent = 'Downloaded!';
                    setTimeout(() => downloadBtnText.textContent = 'Download Image', 2000);
                } catch (err) {
                    alert('Failed to download image. Please try opening the link manually.');
                }
            };
        } else {
            imgBtn.disabled = true;
            imgBtn.classList.add('opacity-50', 'cursor-not-allowed');
            document.getElementById('downloadBtnText').textContent = 'No Image';
        }


        const timeZoneEl = document.getElementById('detailTimeZoneShd');
        if (data.task.time_zone) {
            timeZoneEl.classList.remove('hidden');
            document.getElementById('detailTimeZoneValueShd').textContent = data.task.time_zone;
        } else {
            timeZoneEl.classList.add('hidden');
        }

        const attemptsBody = document.getElementById('attemptsTableBodyShd');
        const noAttempts = document.getElementById('noAttemptsShd');
        attemptsBody.innerHTML = '';
        if (!data.post_attempts || data.post_attempts.length === 0) {
            noAttempts.classList.remove('hidden');
            document.querySelector('#attemptsTableBodyShd').parentElement.classList.add('hidden');
        } else {
            noAttempts.classList.add('hidden');
            document.querySelector('#attemptsTableBodyShd').parentElement.classList.remove('hidden');
            data.post_attempts.forEach(pa => {
                const row = document.createElement('tr');
                row.className = 'hover:bg-neutral-50 transition-all duration-200';
                const aBadge = getStatusBadgeClass(pa.status);
                const platformName = pa.platform ? pa.platform.api_name : (pa.platform_id || 'Unknown');
                row.innerHTML = `
                    <td class="px-5 py-4 whitespace-nowrap text-sm text-neutral-600 font-medium">${platformName}</td>
                    <td class="px-5 py-4 whitespace-nowrap"><span class="px-3 py-1 rounded-full text-xs border font-semibold ${aBadge}">${pa.status}</span></td>
                    <td class="px-5 py-4 whitespace-nowrap text-xs text-neutral-500 font-mono">${formatDate(pa.attempted_at)}</td>
                `;
                attemptsBody.appendChild(row);
            });
        }

        // SECTION 5: ERRORS - Enhanced with expandable terminal-like traceback
        const errorsBody = document.getElementById('errorsTableBodyShd');
        const noErrors = document.getElementById('noErrorsShd');
        errorsBody.innerHTML = '';
        if (!data.error_logs || data.error_logs.length === 0) {
            noErrors.classList.remove('hidden');
            document.querySelector('#errorsTableBodyShd').parentElement.classList.add('hidden');
        } else {
            noErrors.classList.add('hidden');
            document.querySelector('#errorsTableBodyShd').parentElement.classList.remove('hidden');
            data.error_logs.forEach((el, index) => {
                const row = document.createElement('tr');
                row.className = 'hover:bg-neutral-50 transition-all duration-200';
                const traceback = el.details ? el.details.traceback || '' : '';
                const hasTraceback = traceback.trim().length > 0;
                row.innerHTML = `
                    <td class="px-5 py-4 text-sm">
                        <div class="space-y-1">
                            <div class="flex justify-between"><span class="font-semibold text-red-500 block">${el.error_type || 'Error'}</span><span class="text-gray-700" >${formatDate(el.created_at)}</span></div>
                            <span class="block text-neutral-600" title="${el.message}">${el.message || 'No message'}</span>
                            ${el.error_code ? `<span class="block text-neutral-500 text-xs font-mono" title="${el.error_code}">Code: ${el.error_code}</span>` : ''}
                            ${hasTraceback ? `<button style="margin-top:12px" onclick="toggleTraceback(${index})" class="text-gray-600 hover:text-gray-700 bg-gray-50 hover:bg-gray-100 px-2 py-1 rounded-xl border  border-gray-200 transition-all duration-200 inline-flex items-center  hover:shadow-medium">
                                <span id="traceback-toggle-${index}">View Traceback</span>
                                <svg id="traceback-icon-${index}" class="h-3 w-3 ml-1 transform transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                                </svg>
                                
                                </button>
                                <div id="traceback-trcContent-${index}" class="mt-2 hidden">
                                    <div class="terminal-block">${traceback}</div>
                                </div>
                            ` : ''}
                        </div>
                    </td>
                `;
                errorsBody.appendChild(row);
            });
        }

        modalLoading.classList.add('hidden');
        modalContentShd.classList.remove('hidden');

    } catch (error) {
        console.error('Error fetching task details:', error);
        document.getElementById('modalContentShd').innerHTML = `
            <div class="py-16 text-center flex-1 flex flex-col justify-center">
                <svg class="h-12 w-12 text-red-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                <p class="text-red-600 font-semibold text-lg">Failed to load details</p>
                <button onclick="closeModalShd()" class="mt-4 text-sm text-gray-600 hover:underline font-medium">Close</button>
            </div>
        `;
        modalContentShd.classList.remove('hidden');
        modalLoading.classList.add('hidden');
    } finally {
        if(btn) {
            btn.disabled = false;
            if(btnSpinner) btnSpinner.classList.add('hidden');
        }
    }
}

// Terminal-like traceback toggle
function toggleTraceback(index) {
    const toggleBtn = document.getElementById(`traceback-toggle-${index}`);
    const icon = document.getElementById(`traceback-icon-${index}`);
    const trcContent = document.getElementById(`traceback-trcContent-${index}`);
    
    if (trcContent.classList.contains('hidden')) {
        trcContent.classList.remove('hidden');
        toggleBtn.textContent = 'Hide Traceback';
        icon.style.transform = 'rotate(180deg)';
    } else {
        trcContent.classList.add('hidden');
        toggleBtn.textContent = 'View Traceback';
        icon.style.transform = 'rotate(0deg)';
    }
}

function closeModalShd() {
    document.getElementById('taskDetailsModalShd').classList.add('hidden');
    document.body.style.overflow = ''; 
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    fetchTasksShd();

    // Filter Change
    document.getElementById('statusFilterShd').addEventListener('change', (e) => {
        currentStatus = e.target.value;
        currentShdOffset = 0;
        fetchTasksShd(currentStatus, currentShdLimit, currentShdOffset);
    });

    // Pagination
    document.getElementById('prevPageShd').addEventListener('click', () => {
        if (currentShdOffset > 0) {
            currentShdOffset -= currentShdLimit;
            fetchTasksShd(currentStatus, currentShdLimit, currentShdOffset);
        }
    });

    document.getElementById('nextPageShd').addEventListener('click', () => {
        if (currentShdOffset + currentShdLimit < totalTasks) {
            currentShdOffset += currentShdLimit;
            fetchTasksShd(currentStatus, currentShdLimit, currentShdOffset);
        }
    });

    // Close Modal
    document.getElementById('closeModalShd').addEventListener('click', closeModalShd);
    document.getElementById('closeModalBtnFooterShd').addEventListener('click', closeModalShd);

    // Close on Backdrop Click
    document.getElementById('taskDetailsModalShd').addEventListener('click', (e) => {
        if (e.target.id === 'taskDetailsModalShd') {
            closeModalShd();
        }
    });
});