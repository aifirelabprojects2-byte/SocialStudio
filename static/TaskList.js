lucide.createIcons();
const SUPPORTED_PLATFORMSBlz = [
    { 
        id: "instagram", 
        name: "Instagram",
        svg: '<path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>', 
        color: "#E4405F" 
    },
    { 
        id: "facebook", 
        name: "Facebook",
        svg: '<path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>', 
        color: "#1877F2" 
    },
    { 
        id: "linkedin", 
        name: "LinkedIn",
        svg: '<path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.202 24 24 23.227 24 22.271V1.729C24 .774 23.202 0 22.222 0h.003z"/>', 
        color: "#0A66C2" 
    },
    { 
        id: "twitter", 
        name: "Twitter (X)",
        svg: '<path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"/>', 
        color: "#000000" 
    },
    { 
        id: "threads", 
        name: "Threads",
        svg: '<path d="M12.066 0C6.723 0 1.5 3.051 1.5 11.991c0 8.989 5.391 12.009 11.181 12.009 6.045 0 9.384-3.538 9.384-7.612 0-1.916-.915-3.588-2.578-4.706-.62-.415-1.358-.726-1.358-.726-.115-1.703-.621-3.035-1.508-3.966-.887-.932-2.128-1.422-3.591-1.422-2.069 0-3.564.632-4.698 2.253 0 0 1.344.933 1.749 1.203.602-.695 1.076-1.302 2.951-1.302 2.04 0 2.85 1.637 2.85 2.592-.553-.111-1.615-.171-2.495-.171-2.348 0-5.325 1.135-5.325 4.27 0 2.196 2.093 3.873 4.52 3.873 4.164 0 5.112-3.114 5.466-4.965.093 0 1.905 1.034 1.905 3.191 0 3.169-3.105 5.334-7.271 5.334-5.064 0-8.445-3.3-8.445-9.515 0-6.929 3.026-10.185 8.373-10.185 3.235 0 6.765.816 8.425 2.659l2.04-.53C20.325.365 14.535 0 12.066 0z m1.008 16.161c-.836 0-2.4-.435-2.4-1.752 0-.819.396-2.124 3.456-2.124 1.214 0 1.933.098 2.292.242-.247 3.211-1.818 3.634-3.348 3.634z"/>', 
        color: "#000000" 
    }
];

let currentViewBlz = 'list';
let currentPageBlz = 1;
let currentStatusesBlz = [];
let currentChannelsBlz = [];
let totalPagesBlz = 1;

const platformChecksContainerBlz = document.getElementById('platform-checksBlz');
SUPPORTED_PLATFORMSBlz.forEach(plat => {
    const label = document.createElement('label');
    label.className = "flex items-center space-x-3 p-2 border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50 transition-colors";
    label.innerHTML = `
        <input type="checkbox" name="platform-checkBlz" value="${plat.id}" class="form-checkbox rounded text-gray-700 border-slate-300 focus:ring-gray-700 w-4 h-4">
        <div class="w-6 h-6 flex items-center justify-center rounded bg-gray-50 border border-gray-100">
             <svg class="w-4 h-4" fill="${plat.color}" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">${plat.svg}</svg>
        </div>
        <span class="text-sm text-slate-700 font-medium">${plat.name}</span>
    `;
    platformChecksContainerBlz.appendChild(label);
});
document.getElementById('filter-btnBlz').addEventListener('click', (e) => {
    e.stopPropagation();
    document.getElementById('filter-dropdownBlz').classList.toggle('hidden');
});
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('filter-dropdownBlz');
    const btn = document.getElementById('filter-btnBlz');
    if (!dropdown.classList.contains('hidden') && !dropdown.contains(e.target) && !btn.contains(e.target)) {
        dropdown.classList.add('hidden');
    }
});

document.getElementById('prev-pageBlz').addEventListener('click', () => { if (currentPageBlz > 1) { currentPageBlz--; fetchPostsBlz(); } });
document.getElementById('next-pageBlz').addEventListener('click', () => { if (currentPageBlz < totalPagesBlz) { currentPageBlz++; fetchPostsBlz(); } });

function switchViewBlz(view) {
    currentViewBlz = view;
    const btnList = document.getElementById('btn-listBlz');
    const btnGrid = document.getElementById('btn-gridBlz');
    if (view === 'list') {
        btnList.classList.add('bg-brand/10', 'text-brand');
        btnList.classList.remove('text-slate-500');
        btnGrid.classList.remove('bg-brand/10', 'text-brand');
        btnGrid.classList.add('text-slate-500');
    } else {
        btnGrid.classList.add('bg-brand/10', 'text-brand');
        btnGrid.classList.remove('text-slate-500');
        btnList.classList.remove('bg-brand/10', 'text-brand');
        btnList.classList.add('text-slate-500');
    }

    if (window.postsDataBlz && window.postsDataBlz.posts) {
        renderPostsBlz(window.postsDataBlz.posts);
    }
}
function quickFilterBlz(status) {
    const tabs = ['all', 'scheduled', 'posted','draft_approved'];
    tabs.forEach(t => {
        const btn = document.getElementById(`tab-${t}Blz`);
        if (status === t) {
            btn.className = "px-3 py-1.5 text-xs font-medium rounded-md bg-brand/10 text-brand shadow-sm transition-all";
        } else {
            btn.className = "px-3 py-1.5 text-xs font-medium rounded-md text-slate-600 hover:bg-gray-100 transition-all";
        }
    });
    if (status === 'all') {
        currentStatusesBlz = [];
    } else {
        currentStatusesBlz = [status];
    }

    currentPageBlz = 1;
    fetchPostsBlz();
}

function resetFiltersBlz() {
    document.querySelectorAll('input[name="platform-checkBlz"]').forEach(cb => cb.checked = false);
    quickFilterBlz('all');
    document.getElementById('filter-dropdownBlz').classList.add('hidden');
}

function applyFiltersBlz() {
    const platformChecks = document.querySelectorAll('input[name="platform-checkBlz"]:checked');
    currentChannelsBlz = Array.from(platformChecks).map(cb => cb.value);
    currentPageBlz = 1;
    fetchPostsBlz();
    document.getElementById('filter-dropdownBlz').classList.add('hidden');
}
function renderSkeletonBlz() {
    const container = document.getElementById('posts-containerBlz');
    
    if (currentViewBlz === 'list') {
        let rows = '';
        for (let i = 0; i < 5; i++) {
            rows += `
                <tr class="animate-pulse">
                    <td class="p-4"><div class="w-16 h-16 bg-slate-200 rounded-lg mx-auto"></div></td>
                    <td class="p-4">
                        <div class="h-4 bg-slate-200 rounded w-3/4 mb-2"></div>
                        <div class="h-3 bg-slate-100 rounded w-1/2"></div>
                    </td>
                    <td class="p-4">
                        <div class="h-4 bg-slate-200 rounded w-20 mb-2"></div>
                        <div class="h-3 bg-slate-100 rounded w-12"></div>
                    </td>
                    <td class="p-4"><div class="h-6 bg-slate-100 rounded-full w-16 mx-auto"></div></td>
                    <td class="p-4"><div class="h-8 bg-slate-200 rounded-full w-24 mx-auto"></div></td>
                </tr>`;
        }
        container.innerHTML = `
            <div class="bg-white rounded-xl overflow-hidden border border-slate-100">
                <table class="w-full">
                    <tbody class="divide-y divide-slate-50">${rows}</tbody>
                </table>
            </div>`;
    } else {
        let cards = '';
        for (let i = 0; i < 4; i++) {
            cards += `
                <div class="bg-white border border-slate-200 rounded-xl overflow-hidden animate-pulse">
                    <div class="h-40 bg-slate-200"></div>
                    <div class="p-5">
                        <div class="h-4 bg-slate-200 rounded w-3/4 mb-3"></div>
                        <div class="h-3 bg-slate-100 rounded w-full mb-2"></div>
                        <div class="h-3 bg-slate-100 rounded w-2/3"></div>
                        <div class="mt-6 flex justify-between">
                            <div class="h-4 bg-slate-100 rounded w-20"></div>
                            <div class="h-4 bg-slate-100 rounded w-4"></div>
                        </div>
                    </div>
                </div>`;
        }
        container.innerHTML = `<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">${cards}</div>`;
    }
}

function renderEmptyStateBlz() {
    const container = document.getElementById('posts-containerBlz');
    container.innerHTML = `
        <div class="flex flex-col items-center justify-center h-80 bg-white rounded-xl border-2 border-dashed border-slate-200">
            <div class="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
                <i data-lucide="search-x" class="w-8 h-8 text-slate-400"></i>
            </div>
            <h3 class="text-lg font-semibold text-slate-800">No posts found</h3>
            <p class="text-slate-500 text-sm mt-1">Try adjusting your filters or search criteria.</p>
            <button onclick="resetFiltersBlz()" class="mt-4 text-sm font-medium text-brand hover:underline">
                Clear all filters
            </button>
        </div>
    `;
    lucide.createIcons();
}

async function fetchPostsBlz() {
    renderSkeletonBlz();

    const params = new URLSearchParams({
        page: currentPageBlz,
        limit: 10
    });
    if (currentStatusesBlz.length) params.append('statuses', currentStatusesBlz.join(','));
    if (currentChannelsBlz.length) params.append('channels', currentChannelsBlz.join(','));

    try {
        const response = await fetch(`/api/scheduled_posts?${params.toString()}`);
        if (!response.ok) throw new Error("API not found");
        window.postsDataBlz = await response.json();
    } catch (error) {
        // Slight delay so the user doesn't see a "flicker" if the error is instant
        await new Promise(r => setTimeout(r, 400));
        document.getElementById('posts-containerBlz').innerHTML = `
            <div class="flex justify-center items-center h-64 text-slate-500">
                <p>Failed to load posts. Please try again.</p>
            </div>`;
        return; // Stop execution
    }

    // Update Pagination Info (Existing logic)
    totalPagesBlz = Math.ceil(window.postsDataBlz.total / window.postsDataBlz.limit) || 1;
    document.getElementById('page-infoBlz').textContent = `Page ${currentPageBlz} of ${totalPagesBlz}`;
    document.getElementById('prev-pageBlz').disabled = currentPageBlz === 1;
    document.getElementById('next-pageBlz').disabled = currentPageBlz === totalPagesBlz;

    // Render
    renderPostsBlz(window.postsDataBlz.posts);
}

function getStatusBadgeBlz(status) {
    const map = {
        'posted': 'text-emerald-600 border-gray-200',
        'scheduled': 'text-blue-600 border-gray-200',
        'draft_approved': 'text-amber-500 border-gray-200',
    };
    const labelMap = {
        'posted': 'Published',
        'scheduled': 'Scheduled',
        'draft_approved': 'Draft',
    }
    const classes = map[status] || 'bg-gray-100 text-gray-700 border-gray-200';
    const label = labelMap[status] || status;
    
    return `<span class="px-2.5 py-1.5 rounded-full bg-white/40 backdrop-blur-xs text-xs font-medium border border-gray-100 ${classes}">${label}</span>`;
}

async function postNowScheduled(taskId) {
    if (!taskId) return;
    toggleLoading(`postBtnSpr-${taskId}`, true);
    const confirmed = confirm("This task is scheduled.\nDo you want to post it immediately?");
    if (!confirmed) {
        toggleLoading(`postBtnSpr-${taskId}`, false);
        return;
    }
        

    try {
        const res = await fetch(`/task/post-now-scheduled/${taskId}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            }
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || "Failed to post task");
        }
        fetchPostsBlz(); 
    } catch (err) {
        alert(err.message || "Something went wrong");
        toggleLoading(`postBtnSpr-${taskId}`, false);
    } finally {
        toggleLoading(`postBtnSpr-${taskId}`, false);
    }
}


function getActionButtonsBlz(status,task_id) {
    if (status === 'scheduled') {
        return `<button id="postBtnSpr-${task_id}"  onclick="postNowScheduled('${task_id}')" class="border border-gray-200 gap-2 text-gray-600 px-3 py-2.5 rounded-xl text-xs font-medium transition-colors inline-flex hover:scale-95 shadow-sm items-center ">
                    <span>Post Now</span>
                    <i data-lucide="arrow-right" class="w-4 h-4"></i>
        </button>`;
    } else if (status === 'draft_approved') {
        return `<button id="viewBtnApr-${task_id}" onclick="openDetail('${task_id}')" class="border border-gray-200 gap-2 text-gray-600 px-3 py-2.5 rounded-xl text-xs font-medium transition-colors inline-flex hover:scale-95 shadow-sm items-center ">
                    <span>Schedule Now</span>
                    <i data-lucide="chevron-right" class="w-4 h-4"></i>
        </button>`;
    }
    return '';
}

    function getActionButtonsGridBlz(status, task_id) {
        const btnBase =
            "group relative flex items-center justify-end overflow-hidden border border-gray-200 text-gray-600 h-9 rounded-lg shadow-sm transition-all duration-200 hover:scale-95";
    
        const iconCls = "w-4 h-4 flex-shrink-0";
    
        const textCls =
            "absolute right-8 whitespace-nowrap text-xs opacity-0 translate-x-3 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0";
    
        const sizeCls =
            "w-9 group-hover:w-28 px-2"; // expands LEFT because content is right-aligned
    
        if (status === "scheduled") {
            return `
                <button id="postBtnSpr-${task_id}"
                    onclick="postNowScheduled('${task_id}')"
                    data-preserve-html="true"
                    class="${btnBase} ${sizeCls}"
                    title="Post Now">
                    <span class="${textCls}">Post Now</span>
                    <i data-lucide="arrow-right" class="${iconCls}"></i>
                </button>`;
        }
    
        if (status === "draft_approved") {
            return `
                <button id="viewBtnApr-${task_id}"
                    data-preserve-html="true"
                    onclick="openDetail('${task_id}')"
                    class="${btnBase} ${sizeCls}"
                    title="Schedule Now">
                    <span class="${textCls}">Schedule</span>
                    <i data-lucide="chevron-right" class="${iconCls}"></i>
                </button>`;
        }
    
        return "";
    }
        
    


function renderPostsBlz(posts) {
    const container = document.getElementById('posts-containerBlz');
    container.innerHTML = '';

    if (!posts || posts.length === 0) {
        renderEmptyStateBlz();
        return;
    }
    
    if (currentViewBlz === 'list') {
        const tableContainer = document.createElement('div');
        tableContainer.className = 'bg-white rounded-xl overflow-hidden';
        
        const table = document.createElement('table');
        table.className = 'w-full text-left border-collapse';
        table.innerHTML = `
            <thead class="border-b border-slate-200 text-slate-500 text-xs ">
                <tr>
                    <th class="p-4 w-24 text-center">Preview</th>
                    <th class="p-4">Campaign Name</th>
                    <th class="p-4">Date & Time</th>
                    <th class="p-4 text-center">Status</th>
                    <th class="p-4 text-center">Actions</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-100"></tbody>
        `;

        const tbody = table.querySelector('tbody');
        
        posts.forEach(post => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-slate-50 transition-colors group';
            const platformsHtml = post.platforms.map(p => {
                const plat = SUPPORTED_PLATFORMSBlz.find(pl => pl.id === p);
                return plat ? `<div class="w-6 h-6 p-1 bg-gray-50 rounded-full border border-gray-100 flex items-center justify-center mr-1" title="${plat.name}">
                    <svg class="w-full h-full" fill="${plat.color}" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">${plat.svg}</svg>
                </div>` : '';
            }).join('');

            // Date Formatting
            const dateObj = new Date(post.post_date);
            const dateStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            const timeStr = dateObj.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

            row.innerHTML = `
                <td class="p-4 text-center">
                    ${post.preview 
                        ? `<img src="/media/${post.preview}" alt="Preview" class="w-20 h-20 object-cover rounded-lg border border-slate-200 shadow-sm mx-auto">` 
                        : `<div class="w-20 h-20 bg-slate-100 rounded-lg flex items-center justify-center mx-auto text-slate-400"><i data-lucide="image" class="w-5 h-5"></i></div>`}
                </td>
                <td class="p-4">
                    <div class="flex items-center -space-x-1">
                        ${platformsHtml}
                    </div>
                    <div class="hidden text-xs text-slate-400 mt-1">ID: #${post.id || 'N/A'}</div>
                    <div class="font-semibold text-slate-800 text-sm group-hover:text-gray-700 transition-colors">${post.heading}</div>
                    <div class="text-xs text-slate-400 mt-1 w-[600px] text-ellipsis whitespace-nowrap overflow-hidden">${post.content}</div>
                </td>
                <td class="p-4">
                    <div class="text-sm text-slate-700 font-medium">${dateStr}</div>
                    <div class="text-xs text-slate-400">${timeStr}</div>
                </td>
                <td class="p-4 text-center">
                    ${getStatusBadgeBlz(post.status)}
                </td>
                <td class="p-4 text-center">
                     ${getActionButtonsBlz(post.status,post.id)}
                </td>
            `;
            tbody.appendChild(row);
        });

        tableContainer.appendChild(table);
        container.appendChild(tableContainer);
    } else { 
        // Grid View
        const grid = document.createElement('div');
        grid.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6';
        
        posts.forEach(post => {
            const card = document.createElement('div');
            card.className = 'bg-white border border-slate-200 rounded-xl shadow-sm hover:shadow-md transition-shadow flex flex-col overflow-hidden group';
            
            const platformsHtml = post.platforms.map(p => {
                const plat = SUPPORTED_PLATFORMSBlz.find(pl => pl.id === p);
                return plat ? `<svg class="w-4 h-4" fill="${plat.color}" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">${plat.svg}</svg>` : '';
            }).join('');

            const dateObj = new Date(post.post_date);
            const dateStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            const timeStr = dateObj.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

            card.innerHTML = `
                <div class="relative h-40 bg-slate-100 border-b border-slate-100">
                     ${post.preview 
                        ? `<img src="/media/${post.preview}" alt="Preview" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300">` 
                        : `<div class="w-full h-full flex flex-col justify-center items-center text-slate-400"><i data-lucide="image" class="w-10 h-10 mb-2"></i><span class="text-xs">No Preview</span></div>`}
                    <div class="absolute top-3 right-3">
                        ${getStatusBadgeBlz(post.status)}
                    </div>
                </div>
                <div class="p-5 flex-1 flex flex-col">
                    <div class="flex items-center space-x-2 mb-3 bg-slate-50 w-fit px-2 py-1 rounded-full border border-slate-100">
                        ${platformsHtml}
                    </div>
                    <h3 class="font-semibold text-slate-800 mb-2 line-clamp-2 leading-tight group-hover:text-gray-700 transition-colors">${post.content}</h3>
                    
                    <div class="mt-auto pt-4 border-t border-slate-50 flex justify-between items-center text-xs text-slate-500">
                        <div class="flex items-center">
                            <i data-lucide="calendar" class="w-3 h-3 mr-1.5"></i>
                            ${dateStr} at ${timeStr}
                        </div>
                        ${getActionButtonsGridBlz(post.status,post.id)}
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });
        container.appendChild(grid);
    }
    lucide.createIcons();
}
switchViewBlz('list');
fetchPostsBlz(); 
