


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
video: document.getElementById('modalVideo'),
noImg: document.getElementById('modalNoImg'),
imageDownloadBtn: document.getElementById('imageDownloadBtn'),
copyCaptionBtn: document.getElementById('copyCaptionBtn'),
downloadCaptionBtn: document.getElementById('downloadCaptionBtn'),
platforms: document.getElementById('platformsList'),
scheduleSection: document.getElementById('schedulingSection'),
scheduleBtn: document.getElementById('scheduleBtn'),
postNowBtn: document.getElementById('postNowBtn'),
scheduledInput: document.getElementById('scheduledAtInput'),
notes: document.getElementById('notesInput'),
closeBtn: document.getElementById('closeModalBtn'),
inswarn: document.getElementById('inswarn'),
InstaPostType: document.getElementById('InstaPstTyp')

};

function setLoading(bool) {
    if(bool) {
        skeletonDraft.classList.remove('hidden')
        els.tbody.classList.add('hidden'); 
    } else {
        skeletonDraft.classList.add('hidden')
        els.tbody.classList.remove('hidden');
    }
}
function isVideoFile(url) {
    if (!url) return false;
    const cleanUrl = url.split('?')[0].toLowerCase();
    return cleanUrl.endsWith('.mp4') || 
           cleanUrl.endsWith('.mov') || 
           cleanUrl.endsWith('.webm') || 
           cleanUrl.endsWith('.ogg');
}

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

        // --- UPDATED MEDIA LOGIC START ---
        
        // Reset both
        els.img.style.display = 'none';
        els.img.src = '';
        els.video.style.display = 'none';
        els.video.src = '';
        els.video.pause(); // Ensure audio stops if previously playing

        const mediaUrl = d.preview_image || d.media_url; // Handle potential naming differences

        if (mediaUrl) {
            els.noImg.classList.add('hidden');
            els.noImg.style.display = 'none'; 
            els.imageDownloadBtn.classList.remove('hidden');

            if (isVideoFile(mediaUrl)) {
                // It is a video
                els.video.src = mediaUrl;
                els.video.style.display = 'block';
            } else {
                // It is an image
                els.img.src = mediaUrl;
                els.img.style.display = 'block';
            }
        } else {
            // No media
            els.noImg.classList.remove('hidden');
            els.noImg.style.display = 'flex'; 
            els.imageDownloadBtn.classList.add('hidden');
        }
        // --- UPDATED MEDIA LOGIC END ---

        // Define getFullCaptionText for caption actions
        const getFullCaptionText = () => {
            const content = els.content.textContent || '';
            const hashtags = els.hashtags.textContent || '';
            const now = new Date().toLocaleString();
            return `${now}\n\nCaption:\n${content}\n\nHashtags:\n${hashtags}`;
        };

        // --- UPDATED DOWNLOAD BUTTON LOGIC START ---
        els.imageDownloadBtn.onclick = (e) => {
            e.stopPropagation();
            
            // Determine which source is active
            const activeSrc = els.video.style.display === 'block' ? els.video.src : els.img.src;
            
            if (activeSrc) {
                const isVid = isVideoFile(activeSrc);
                const ext = isVid ? 'mp4' : 'jpg'; // Default extensions
                
                const a = document.createElement('a');
                a.href = activeSrc;
                a.download = `task-media-${Date.now()}.${ext}`;
                a.target = "_blank"; // Good practice for some browsers to force download
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }
        };

        els.copyCaptionBtn.onclick = async (e) => {
            e.stopPropagation();
            try {
                const text = getFullCaptionText();
                await navigator.clipboard.writeText(text);
                const originalText = els.copyCaptionBtn.innerHTML;
                els.copyCaptionBtn.innerHTML = '<svg class="w-4 h-4 text-gray-600" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4.89163 13.2687L9.16582 17.5427L18.7085 8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
                setTimeout(() => { els.copyCaptionBtn.innerHTML = originalText; }, 2000);
            } catch (err) {
                console.error('Failed to copy: ', err);
                // Fallback for older browsers or non-secure contexts
                if (els.content) {
                    const textArea = document.createElement('textarea');
                    textArea.value = getFullCaptionText();
                    document.body.appendChild(textArea);
                    textArea.select();
                    try {
                        document.execCommand('copy');
                        const originalText = els.copyCaptionBtn.innerHTML;
                        els.copyCaptionBtn.innerHTML = '<svg class="w-4 h-4 text-gray-600" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4.89163 13.2687L9.16582 17.5427L18.7085 8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
                        setTimeout(() => { els.copyCaptionBtn.innerHTML = originalText; }, 2000);
                    } catch (fallbackErr) {
                        console.error('Fallback copy failed: ', fallbackErr);
                        alert('Failed to copy to clipboard. Please select and copy manually.');
                    }
                    document.body.removeChild(textArea);
                }
            }
        };

        els.downloadCaptionBtn.onclick = (e) => {
            e.stopPropagation();
            const fullText = getFullCaptionText();
            const blob = new Blob([fullText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `task-caption-${Date.now()}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        };

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
        els.postNowBtn.onclick = () => handlePostNow(task_id);

        els.overlaymodal.classList.remove('hidden');
    } catch (e) {
        console.error(e);
        alert("Could not load details");
        toggleLoading(`viewBtnApr-${taskId}`, false);
    } finally {
        toggleLoading(`viewBtnApr-${taskId}`, false);
    }
}
// 1. Define Platform Icons & Colors (derived from your reference)
const PLATFORM_ICONS = {
    instagram: {
        color: "text-pink-600",
        path: "M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"
    },
    facebook: {
        color: "text-blue-600",
        path: "M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036c-2.148 0-2.797 1.66-2.797 3.54v1.237h3.362l-.294 3.667h-3.068v7.98H9.101z"
    },
    linkedin: {
        color: "text-sky-700",
        path: "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.202 24 24 23.227 24 22.271V1.729C24 .774 23.202 0 22.222 0h.003z"
    },
    twitter: {
        color: "text-gray-900",
        path: "M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"
    },
    x: { // Handle both naming conventions
        color: "text-gray-900",
        path: "M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"
    },
    threads: {
        color: "text-black",
        path: "M9.4815 9.024c-.405-.27-1.749-1.203-1.749-1.203 1.134-1.6215 2.6295-2.253 4.698-2.253 1.4625 0 2.7045.4905 3.591 1.422.8865.9315 1.392 2.2635 1.5075 3.966q.738.3105 1.3575.726c1.6635 1.1175 2.5785 2.79 2.5785 4.7055 0 4.074-3.339 7.6125-9.384 7.6125C6.891 24 1.5 20.9805 1.5 11.991 1.5 3.051 6.723 0 12.066 0c2.469 0 8.259.3645 10.434 7.554l-2.04.5295C18.774 2.961 15.2445 2.145 12.009 2.145c-5.3475 0-8.373 3.2565-8.373 10.185 0 6.2145 3.381 9.5145 8.445 9.5145 4.1655 0 7.2705-2.1645 7.2705-5.334 0-2.157-1.812-3.1905-1.905-3.1905-.354 1.851-1.302 4.965-5.466 4.965-2.427 0-4.5195-1.677-4.5195-3.873 0-3.135 2.976-4.2705 5.325-4.2705.879 0 1.941.06 2.4945.171 0-.9555-.81-2.592-2.85-2.592-1.875 0-2.349.6075-2.9505 1.302ZM13.074 12.285c-3.06 0-3.456 1.305-3.456 2.124 0 1.317 1.5645 1.752 2.4 1.752 1.53 0 3.1005-.423 3.348-3.6345a9.3 9.3 0 0 0-2.292-.2415"
    }
};

function populatePlatforms(platforms) {
    els.platforms.innerHTML = ''; 

    // 1. Empty State
    if (!platforms || platforms.length === 0) {
        els.platforms.classList.remove("grid", "grid-cols-1", "sm:grid-cols-2", "gap-3");
        els.platforms.classList.add('flex');
        
        const emptyMessage = document.createElement('div');
        emptyMessage.className = "w-full";
        emptyMessage.innerHTML = `
            <div class="rounded-xl border border-dashed border-gray-200 bg-gray-50/50 p-6 text-center">
                <svg class="mx-auto h-8 w-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                <h3 class="mt-2 text-sm font-medium text-gray-900">No Platforms Connected</h3>
                <p class="mt-1 text-xs text-gray-500">Go to Settings to connect an account.</p>
            </div>
        `;
        els.platforms.appendChild(emptyMessage);
        els.inswarn.classList.add('hidden');
        return;
    }

    // 2. Restore Grid Layout
    els.platforms.classList.add("grid", "grid-cols-1", "sm:grid-cols-2", "gap-3");
    els.platforms.classList.remove('flex');

    // 3. Render Platform Cards
    platforms.forEach(p => {
        const platformId = p.platform_id;
        const apiName = p.api_name || 'unknown';
        const accName = p.account_name || 'Connected Account';
        const photoUrl = p.profile_photo_url;
        const fallback = 'https://www.gravatar.com/avatar/0?d=mp';
        
        const iconData = PLATFORM_ICONS[apiName.toLowerCase()] || { path: '', color: 'text-gray-400' };
        const initials = accName.substring(0, 2).toUpperCase();

        const div = document.createElement('div');
        div.className = 'relative group';
        
        let avatarHtml = '';
        if (photoUrl) {
            avatarHtml = `<img src="${photoUrl}" onerror="this.onerror=null; this.src='${fallback}'" alt="${accName}" class="h-full w-full object-cover">`;
        } else {
            const colors = {
                'instagram': 'bg-pink-100 text-pink-700',
                'facebook': 'bg-blue-100 text-blue-700',
                'linkedin': 'bg-sky-100 text-sky-700',
                'twitter': 'bg-gray-100 text-gray-700',
                'x': 'bg-gray-100 text-gray-700'
            };
            const colorClass = colors[apiName.toLowerCase()] || 'bg-gray-100 text-gray-600';
            avatarHtml = `<div class="${colorClass} w-full h-full flex items-center justify-center text-xs font-bold">${initials}</div>`;
        }

        div.innerHTML = `
            <input type="checkbox" id="platform-toggle-${platformId}" value="${platformId}" class="peer sr-only">
            
            <div class="flex items-center gap-3 p-3 rounded-xl border border-gray-200 bg-white  cursor-pointer
                        hover:border-gray-300 hover:shadow-sm
                        peer-checked:border-gray-900 peer-checked:bg-gray-50 peer-checked:ring-1 peer-checked:ring-gray-900
                        peer-checked:[&_.checkbox-circle]:bg-gray-900 peer-checked:[&_.checkbox-circle]:border-gray-900
                        peer-checked:[&_.check-icon]:opacity-100 peer-checked:[&_.check-icon]:scale-100">
                
                <div class="relative shrink-0">
                    <div class="h-10 w-10 overflow-hidden rounded-full border border-gray-100 shadow-sm">
                        ${avatarHtml}
                    </div>
                    ${iconData.path ? `
                    <div class="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full border border-gray-100 bg-white shadow-sm ring-1 ring-white">
                        <svg class="h-3 w-3 ${iconData.color}" fill="currentColor" viewBox="0 0 24 24">
                            <path d="${iconData.path}" />
                        </svg>
                    </div>
                    ` : ''}
                </div>

                <div class="flex-1 min-w-0">
                    <p class="text-sm font-semibold text-gray-900 truncate leading-tight">
                        ${escapeHtml(accName)}
                    </p>
                    <p data-platform="${apiName}" class="text-[11px] font-medium text-gray-500 capitalize leading-tight mt-0.5">
                        ${apiName}
                    </p>
                </div>

                <div class="checkbox-circle h-5 w-5 shrink-0 rounded-full border border-gray-300 bg-white flex items-center justify-center  duration-200">
                    <svg class="check-icon w-3 h-3 text-white opacity-0 transform scale-50  duration-200" 
                         fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                </div>
            </div>

            <label for="platform-toggle-${platformId}" class="absolute inset-0 cursor-pointer"></label>
        `;
        
        els.platforms.appendChild(div);
    });

    const inputs = els.platforms.querySelectorAll('input[type="checkbox"]');
    inputs.forEach(input => {
        input.addEventListener('change', checkPlatformWarnings);
    });
}
function checkPlatformWarnings() {
    const checked = Array.from(els.platforms.querySelectorAll('input:checked'));
    
    const hasInsta = checked.some(cb => {
        const container = cb.closest('.group'); 
        const platformEl = container.querySelector('[data-platform]');
        const platformName = platformEl ? platformEl.dataset.platform.toLowerCase() : '';
        return platformName === 'instagram';
    });
    const isImgVisible = els.img.src && els.img.style.display !== 'none';
    const isVideoVisible = els.video.style.display === 'block' && 
                        (els.video.src || els.video.querySelector('source'));

    const hasMedia = isImgVisible || isVideoVisible;
    els.InstaPostType.classList.toggle('hidden', !hasInsta);
    els.inswarn.classList.toggle('hidden', !(hasInsta && !hasMedia));
}
function getSelectedInstaPostType() {
    const selected = document.querySelector('input[name="InspostType"]:checked');
    if (selected) {
        return selected.value;  
    } else {
        return null; 
    }
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
        ShowNoti('info', 'Please select a scheduled date and time');
        return;
    }
    const scheduledAt = new Date(scheduledAtStr).toISOString();

    const notes = getSelectedInstaPostType();

    const requestBody = {
        task_id: taskId,
        platform_ids: platformIds,
        scheduled_at: scheduledAt,
        notes: notes || null
    };
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
        ShowNoti('success', 'Task scheduled successfully!');
        closeModalSch();
    } catch (e) {
        console.error(e);
        alert(`Error: ${e.message}`);
    } finally {
        els.scheduleBtn.innerText = originalBtnText;
        els.scheduleBtn.disabled = false;
        fetchPostsBlz()
    }
}

async function handlePostNow(taskId) {
    const platformCheckboxes = document.querySelectorAll('#platformsList input[type="checkbox"]:checked');
    const platformIds = Array.from(platformCheckboxes).map(cb => cb.value);

    if (platformIds.length === 0) {
        ShowNoti('info', 'Please select at least one platform');
        return;
    }

    const scheduledAtStr = els.scheduledInput.value;
    if (!scheduledAtStr) {
        ShowNoti('info', 'Please select a scheduled date and time');
        return;
    }

    const scheduledAt = new Date(scheduledAtStr).toISOString();

    const notes = getSelectedInstaPostType();

    const requestBody = {
        task_id: taskId,
        platform_ids: platformIds,
        scheduled_at: scheduledAt,
        notes: notes || undefined
    };
    console.warn(requestBody);
    

    const originalBtnText = els.postNowBtn.innerText;
    els.postNowBtn.innerText = 'Posting...';
    els.postNowBtn.disabled = true;

    try {
        const res = await fetch('/task/post-now', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to schedule task');
        }
        const data = await res.json();
        closeModalSch();
    } catch (e) {
        console.error(e);
        alert(`Error: ${e.message}`);
    } finally {
        els.postNowBtn.innerText = originalBtnText;
        els.postNowBtn.disabled = false;
        fetchPostsBlz();
    }
}


function closeModalSch() {
    els.overlaymodal.classList.add('hidden');
    els.scheduleSection.classList.add('hidden');
    els.scheduleBtn.classList.add('hidden');
    els.platforms.innerHTML = '';
    els.notes.value = '';
    els.scheduledInput.value = '';
    els.img.src = '';
    els.imageDownloadBtn.classList.add('hidden');
}

els.closeBtn.onclick = closeModalSch;

function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
