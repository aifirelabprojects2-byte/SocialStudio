
const elsCft = {
    mainCard: document.getElementById('mainCardCft'),
    cardSpinner: document.getElementById('cardSpinnerCft'),
    openFetchBtn: document.getElementById('openFetchBtnCft'),
    globalStatus: document.getElementById('globalStatusCft'),
    emptyState: document.getElementById('emptyStateCft'),
    emptyInput: document.getElementById('emptyInputCft'),
    emptyFetchBtn: document.getElementById('emptyFetchBtnCft'),
    
    // View Mode
    viewMode: document.getElementById('viewModeCft'),
    vName: document.getElementById('vNameCft'),
    vUrl: document.getElementById('vUrlCft'),
    vLoc: document.getElementById('vLocCft'),
    vDetails: document.getElementById('vDetailsCft'),
    vProducts: document.getElementById('vProductsCft'),
    
    // Edit Mode
    editMode: document.getElementById('editModeCft'),
    eName: document.getElementById('eNameCft'),
    eLoc: document.getElementById('eLocCft'),
    eDesc: document.getElementById('eDescCft'),
    eSave: document.getElementById('eSaveCft'),
    eRevert: document.getElementById('eRevertCft'),

    // Tabs
    tabView: document.getElementById('tabViewCft'),
    tabEdit: document.getElementById('tabEditCft'),

    // Modal
    modal: document.getElementById('popupModalCft'),
    modalInput: document.getElementById('modalInputCft'),
    modalFetchBtn: document.getElementById('modalFetchBtnCft'),
    dismissBtns: document.getElementById('dismissBtnsCft'),
    askLaterBtn: document.getElementById('askLaterBtnCft'),
    dontAskBtn: document.getElementById('dontAskBtnCft'),
    closeModalBtn: document.getElementById('closeModalBtnCft'),
    modalErr: document.getElementById('modalErrCft')
};

let currentCompanyCft = null;
let globalStatusTimeoutCft = null;

// Initialize Icons
const refreshIconsCft = () => {
    if (window.lucide) {
        window.lucide.createIcons();
    }
};

const toggleMainViewCft = (state) => {
    // 1. Reset everything to a "dead" state
    // We remove 'flex' and add 'hidden' to both main containers
    elsCft.emptyState.classList.add('hidden');
    elsCft.emptyState.classList.remove('flex');
    
    elsCft.mainCard.classList.add('hidden');
    
    // Hide all sub-states inside the main card
    elsCft.cardSpinner.classList.add('hidden');
    elsCft.cardSpinner.classList.remove('flex');
    elsCft.viewMode.classList.add('hidden');
    elsCft.editMode.classList.add('hidden');

    // 2. Activate only the requested state
    if (state === 'empty') {
        elsCft.emptyState.classList.remove('hidden');
        elsCft.emptyState.classList.add('flex'); // Restore layout
        elsCft.openFetchBtn.classList.add('hidden');
    } 
    else if (state === 'loading') {
        elsCft.mainCard.classList.remove('hidden');
        elsCft.cardSpinner.classList.remove('hidden');
        elsCft.cardSpinner.classList.add('flex'); // Restore layout
        elsCft.openFetchBtn.classList.add('hidden');
    } 
    else if (state === 'data') {
        elsCft.mainCard.classList.remove('hidden');
        elsCft.viewMode.classList.remove('hidden');
        elsCft.openFetchBtn.classList.remove('hidden');
    }
    
    refreshIconsCft();
};

// --- Utils ---
const showStatusCft = (msg, type = 'info', autoHide = true) => {
    let baseClasses =
      "m-8 rounded-2xl p-4 text-sm font-medium border shadow-sm flex items-start gap-3 fade-enter-cft";
    let colors = "";
    let iconName = "info";

    if (type === 'error') {
        colors = 'bg-gray-50 dark:bg-gray-900/20 text-gray-700 dark:text-gray-200 border-gray-100 dark:border-gray-900/30';
        iconName = "alert-octagon";
    } else if (type === 'success') {
        colors = 'bg-gray-50 dark:bg-gray-900/20 text-gray-700 dark:text-gray-200 border-gray-100 dark:border-gray-900/30';
        iconName = "check-circle";
    } else {
        colors = 'bg-gray-50 dark:bg-gray-900/20 text-gray-700 dark:text-gray-200 border-gray-100 dark:border-gray-900/30';
        iconName = "info";
    }

    // Clear previous timer (important)
    if (globalStatusTimeoutCft) {
        clearTimeout(globalStatusTimeoutCft);
        globalStatusTimeoutCft = null;
    }

    elsCft.globalStatus.className = `${baseClasses} ${colors}`;
    elsCft.globalStatus.innerHTML = `
        <i data-lucide="${iconName}" class="w-5 h-5 flex-shrink-0 mt-0.5"></i>
        <span>${msg}</span>
    `;
    elsCft.globalStatus.classList.remove('hidden');

    refreshIconsCft();

    // Auto-hide after 3s
    if (autoHide) {
        globalStatusTimeoutCft = setTimeout(() => {
            elsCft.globalStatus.classList.add('hidden');
        }, 3000);
    }
};

const escapeHtmlCft = (unsafe) => {
    if(!unsafe) return '';
    return unsafe.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
};

// --- Render Functions ---
const renderViewCft = (c) => {
    elsCft.vName.textContent = c.company_name || 'Unknown Name';
    elsCft.vUrl.href = c.website_url;
    try {
        elsCft.vUrl.querySelector('span').textContent = new URL(c.website_url).hostname;
    } catch(e) { elsCft.vUrl.querySelector('span').textContent = c.website_url; }
    
    const loc = c.company_location || 'Not listed';
    elsCft.vLoc.textContent = loc;
    
    elsCft.vDetails.textContent = c.company_details || 'No description available.';

    const prods = c.company_products || [];
    if(prods.length === 0) {
        elsCft.vProducts.innerHTML = `
            <div class="col-span-full py-8 text-center border-2 border-dashed border-gray-200 dark:border-gray-800 rounded-2xl">
                <p class="text-gray-400 dark:text-gray-500 italic text-sm">No products found.</p>
            </div>`;
    } else {
        elsCft.vProducts.innerHTML = prods.map(p => `
            <div class="border border-zinc-200 dark:border-gray-800 rounded-2xl p-5 hover:shadow-md bg-gray-50 dark:bg-gray-800/50 transition-all duration-300 group">
                <div class="font-semibold text-gray-900 dark:text-white text-base mb-2 group-hover:text-brand dark:group-hover:text-brand transition-colors">${escapeHtmlCft(p.name)}</div>
                <div class="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">${escapeHtmlCft(p.description)}</div>
            </div>
        `).join('');
    }
    refreshIconsCft();
};

const populateEditCft = (c) => {
    elsCft.eName.value = c.company_name || '';
    elsCft.eLoc.value = c.company_location || '';
    elsCft.eDesc.value = c.company_details || '';
};

// --- Tab Logic ---
const setTabCft = (mode) => {
    const activeClass = ['bg-white', 'dark:bg-gray-700', 'text-gray-900', 'dark:text-white', 'shadow'];
    const inactiveClass = ['text-gray-500', 'dark:text-gray-400', 'hover:text-gray-700', 'dark:hover:text-gray-200', 'hover:bg-gray-200/50', 'dark:hover:bg-gray-700/50'];

    const resetBtn = (btn) => {
        btn.className = "flex items-center justify-center gap-2 rounded-full py-2 px-3 text-sm font-medium transition-all duration-200";
    };

    resetBtn(elsCft.tabView);
    resetBtn(elsCft.tabEdit);

    if(mode === 'view') {
        elsCft.viewMode.classList.remove('hidden');
        elsCft.editMode.classList.add('hidden');
        
        elsCft.tabView.classList.add(...activeClass, 'font-semibold');
        elsCft.tabEdit.classList.add(...inactiveClass);
        
        if(currentCompanyCft) renderViewCft(currentCompanyCft);
    } else {
        elsCft.viewMode.classList.add('hidden');
        elsCft.editMode.classList.remove('hidden');
        
        elsCft.tabEdit.classList.add(...activeClass, 'font-semibold');
        elsCft.tabView.classList.add(...inactiveClass);
    }
};
elsCft.tabView.onclick = () => setTabCft('view');
elsCft.tabEdit.onclick = () => setTabCft('edit');

// --- Modal Logic ---

elsCft.modalInput.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    if(val.length > 0) {
        elsCft.dismissBtns.classList.add('opacity-0', 'pointer-events-none');
    } else {
        elsCft.dismissBtns.classList.remove('opacity-0', 'pointer-events-none');
    }
});

const openModalCft = (isManual = false) => {
    elsCft.modalInput.value = '';
    elsCft.modalErr.textContent = '';
    elsCft.dismissBtns.classList.remove('opacity-0', 'pointer-events-none'); 
    
    if(isManual) {
        elsCft.dismissBtns.classList.add('hidden');
        elsCft.closeModalBtn.classList.remove('hidden');
    } else {
        elsCft.dismissBtns.classList.remove('hidden');
        elsCft.closeModalBtn.classList.add('hidden');
    }
    elsCft.modal.classList.remove('hidden');
    refreshIconsCft();
};

elsCft.askLaterBtn.onclick = () => {
    const ts = Date.now() + (24 * 60 * 60 * 1000);
    localStorage.setItem('cmp_ask_later_Cft', ts);
    elsCft.modal.classList.add('hidden');
};
elsCft.dontAskBtn.onclick = () => {
    localStorage.setItem('cmp_dont_ask_Cft', 'true');
    elsCft.modal.classList.add('hidden');
};
elsCft.closeModalBtn.onclick = () => elsCft.modal.classList.add('hidden');

const initCft = async () => {
    refreshIconsCft();
    try {
        const res = await fetch('/api/company');
        const data = await res.json();

        if(data.exists) {
            currentCompanyCft = data.company;
            renderViewCft(currentCompanyCft);
            populateEditCft(currentCompanyCft);
            toggleMainViewCft('data');
            setTabCft('view');
        } else {
            toggleMainViewCft('empty');
            const dont = localStorage.getItem('cmp_dont_ask_Cft');
            const later = localStorage.getItem('cmp_ask_later_Cft');
            let showModal = true;
            if(dont === 'true') showModal = false;
            if(later && parseInt(later) > Date.now()) showModal = false;

            if(showModal) openModalCft(false);
        }
    } catch(e) {
        showStatusCft('Server connection failed.', 'error');
    }
};

const handleFetchActionCft = async (urlInput) => {
    elsCft.modal.classList.add('hidden');
    ShowNoti("info","This action is disabled in demo mode");
};

elsCft.modalFetchBtn.onclick = () => handleFetchActionCft(elsCft.modalInput);
elsCft.emptyFetchBtn.onclick = () => handleFetchActionCft(elsCft.emptyInput);



elsCft.eSave.onclick = async () => {
    if(!currentCompanyCft) return;
    ShowNoti("info","This action is disabled in demo mode");
};

elsCft.eRevert.onclick = () => populateEditCft(currentCompanyCft);
elsCft.openFetchBtn.onclick = () => openModalCft(true);
window.addEventListener('load', initCft);

document.getElementById('deleteCompanyBtnCft')
  ?.addEventListener('click', deleteCompany);


async function deleteCompany() {
  if (!confirm("Are you sure you want to delete company details?")) return;

  try {
    const res = await fetch("/api/company", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" }
    });

    const data = await res.json();
    if (!res.ok) throw new Error("Delete failed");

    currentCompanyCft = null;
    toggleMainViewCft('empty');

    showStatusCft("Company profile deleted successfully.", "success");

    // Optional: ask again later
    localStorage.removeItem('cmp_dont_ask_Cft');
    localStorage.removeItem('cmp_ask_later_Cft');

  } catch (err) {
    console.error(err);
    showStatusCft("Error deleting company profile.", "error");
  }
}
