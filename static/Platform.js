const apiBasePls = '/api/platforms';
let currentPlatformPls = null;
const getSpinnerPls = () => `<div class="spinner-pls h-3 w-3 inline-block ml-1"></div>`;

function getPlatformIconPls(name) {
    const icons = {
      facebook: `<svg class="h-6 w-6" fill="currentColor" viewBox="0 0 24 24" id="facebook" data-name="Line Color" xmlns="http://www.w3.org/2000/svg" class="icon line-color"><path id="primary" d="M14,7h4V3H14A5,5,0,0,0,9,8v3H6v4H9v6h4V15h3l1-4H13V8A1,1,0,0,1,14,7Z" style="fill: none; stroke: rgb(0, 0, 0); stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.5;"></path></svg>`,
      x: `<svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z"/></svg>`,
      instagram: `<svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>`,
      threads: `<svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" shape-rendering="geometricPrecision" text-rendering="geometricPrecision" image-rendering="optimizeQuality" fill-rule="evenodd" clip-rule="evenodd" viewBox="0 0 440 511.43"><path fill="currentColor" fill-rule="nonzero" d="M342.383 237.038a177.282 177.282 0 00-6.707-3.046c-3.948-72.737-43.692-114.379-110.429-114.805-38.505-.255-72.972 15.445-94.454 48.041l36.702 25.178c15.265-23.159 39.221-28.096 56.864-28.096.204 0 .408 0 .61.002 21.974.14 38.555 6.529 49.287 18.987 7.81 9.071 13.034 21.606 15.621 37.425-19.483-3.311-40.553-4.329-63.077-3.038-63.45 3.655-104.24 40.661-101.501 92.08 1.391 26.083 14.385 48.523 36.587 63.181 18.772 12.391 42.95 18.45 68.077 17.079 33.183-1.819 59.215-14.48 77.377-37.63 13.793-17.58 22.516-40.363 26.368-69.069 15.814 9.544 27.535 22.103 34.007 37.2 11.006 25.665 11.648 67.84-22.764 102.223-30.15 30.121-66.392 43.151-121.164 43.554-60.758-.45-106.708-19.935-136.583-57.915-27.976-35.562-42.434-86.93-42.973-152.674.539-65.746 14.997-117.114 42.973-152.676 29.875-37.979 75.824-57.463 136.582-57.914 61.197.455 107.948 20.033 138.967 58.195 15.21 18.713 26.676 42.248 34.236 69.688L440 161.532c-9.163-33.775-23.582-62.881-43.203-87.017C357.031 25.59 298.872.519 223.936 0h-.3C148.851.518 91.344 25.683 52.709 74.795 18.331 118.499.598 179.308.002 255.535l-.002.18.002.18c.596 76.225 18.329 137.037 52.707 180.741 38.635 49.11 96.142 74.277 170.927 74.794h.3c66.486-.462 113.352-17.868 151.96-56.442 50.51-50.463 48.99-113.718 32.342-152.549-11.945-27.847-34.716-50.463-65.855-65.401zM227.587 344.967c-27.808 1.567-56.699-10.916-58.124-37.651-1.056-19.823 14.108-41.942 59.831-44.577a266.87 266.87 0 0115.422-.45c16.609 0 32.145 1.613 46.271 4.701-5.268 65.798-36.172 76.483-63.4 77.977z"/></svg>`
    };

    return icons[name.toLowerCase()] || `<span>${name.charAt(0).toUpperCase()}</span>`;
  }

async function loadPlatformsPls() {
  const refreshBtnPls = document.getElementById('refreshBtnPls');
  if(refreshBtnPls) {
    refreshBtnPls.innerHTML = `Refreshing... ${getSpinnerPls()}`;
    refreshBtnPls.disabled = true;
  }

  try {
    const resPls = await fetch(`${apiBasePls}/list`);
    const platformsPls = await resPls.json();
    const tbodyPls = document.getElementById('platformTableBodyPls');
    tbodyPls.innerHTML = '';

    platformsPls.forEach(pPls => {
      const trPls = document.createElement('tr');
      
      let daysTextPls = 'Never';
      let daysClassPls = 'text-gray-400 font-normal italic';
      let statusBadgePls = '';
    
      if (pPls.days_remaining !== null) {
        const daysPls = pPls.days_remaining;
        daysTextPls = `${daysPls} day${daysPls === 1 ? '' : 's'}`;
    
        if (daysPls < 0) {
          daysTextPls = `Expired ${Math.abs(daysPls)}d ago`;
          daysClassPls = 'text-gray-900 font-bold';
        } else if (daysPls < 5) {
          daysClassPls = 'text-gray-900 font-semibold';
        } else {
          daysClassPls = 'text-gray-600';
        }
      }
      const activeClassPls = pPls.is_active 
        ? 'bg-black text-white ring-1 ring-inset ring-black' 
        : 'bg-gray-100 text-gray-600 ring-1 ring-inset ring-gray-500/10';

      const tokenStatusPls = (pPls.has_token && pPls.has_token[pPls.name.toLowerCase()]) 
        ? '<span class="inline-flex items-center gap-x-1.5 py-0.5 px-2 rounded-2xl text-xs font-medium text-gray-900 ring-1 ring-inset ring-gray-200 bg-white">Configured</span>'
        : '<span class="inline-flex items-center gap-x-1.5 py-0.5 px-2 rounded-2xl text-xs font-medium text-gray-500 ring-1 ring-inset ring-gray-100 bg-gray-50">Missing</span>';
      
      const platformIconHtml = getPlatformIconPls(pPls.name);
      trPls.innerHTML = `
        <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
          <div class="flex items-center">
            <!-- Platform Icon Placeholder -->
            <div class="h-8 w-8 rounded-full bg-white flex items-center justify-center text-gray-900 mr-3 border border-gray-200 shadow-sm">
                ${platformIconHtml}
            </div>
            ${pPls.name.charAt(0).toUpperCase() + pPls.name.slice(1)}
          </div>
        </td>
        <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
          <span class="inline-flex items-center rounded-2xl px-2 py-1 text-xs font-medium ${activeClassPls}">
            ${pPls.is_active ? 'Active' : 'Inactive'}
          </span>
        </td>
        <td class="whitespace-nowrap px-3 py-4 text-sm">
          <div class="${daysClassPls}">${daysTextPls}</div>
          <div class="text-xs text-gray-400 mt-0.5">${pPls.expires_at_local || ''}</div>
        </td>
        <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
          ${tokenStatusPls}
        </td>
        <td class="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
          <button onclick="openEditPls('${pPls.name.toLowerCase()}', this)" class="text-black hover:text-gray-600 transition-colors border border-gray-300 rounded px-3 py-1 text-xs hover:bg-gray-50 bg-white">
            Edit
          </button>
        </td>
      `;
      tbodyPls.appendChild(trPls);
    });
  } catch (err) {
    console.error("Failed to load platforms", err);
  } finally {
    if(refreshBtnPls) {
      refreshBtnPls.innerHTML = 'Refresh Data';
      refreshBtnPls.disabled = false;
    }
  }
}

async function openEditPls(namePls, btnElementPls) {
    currentPlatformPls = namePls;
    const originalTextPls = btnElementPls.innerHTML;
    btnElementPls.innerHTML = `<div class="spinner-pls h-3 w-3 border-gray-900"></div>`;
    btnElementPls.disabled = true;

    try {
        const resPls = await fetch(`${apiBasePls}/${namePls}`);
        const dataPls = await resPls.json();
      
        document.getElementById('modalTitlePls').textContent = `Configure ${dataPls.name}`;
        document.getElementById('isActivePls').checked = dataPls.is_active;
        document.getElementById('expiresAtPls').value = dataPls.expires_at || '';
      
        const fieldsContainerPls = document.getElementById('platformFieldsPls');
        fieldsContainerPls.innerHTML = '';
        const addFieldPls = (labelPls, idPls, typePls = 'text', valuePls = '', isPasswordPls = false) => {
            const divPls = document.createElement('div');
            let inputHtmlPls = `<input type="${typePls}" id="${idPls}Pls" value="${valuePls || ''}" placeholder="Leave blank to keep unchanged" class="block w-full rounded-2xl border-0 py-2 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-black sm:text-sm sm:leading-6 pr-9 px-3"/>`;
            
            if (isPasswordPls) {
              inputHtmlPls = `
                <div class="relative mt-2">
                  ${inputHtmlPls}
                  <button type="button" class="absolute inset-y-0 right-0 flex items-center pr-3" onclick="togglePasswordPls(this)">
                      <svg class="h-4 w-4 text-gray-400 hover:text-gray-600 eye-open-pls" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      <svg class="h-4 w-4 text-gray-400 hover:text-gray-600 hidden eye-slash-pls" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M4 4L20 20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                      <path fill-rule="evenodd" clip-rule="evenodd" d="M6.22308 5.63732C4.19212 6.89322 2.60069 8.79137 1.73175 11.0474C1.49567 11.6604 1.49567 12.3396 1.73175 12.9526C3.31889 17.0733 7.31641 20 12 20C14.422 20 16.6606 19.2173 18.4773 17.8915L17.042 16.4562C15.6033 17.4309 13.8678 18 12 18C8.17084 18 4.89784 15.6083 3.5981 12.2337C3.54022 12.0835 3.54022 11.9165 3.5981 11.7663C4.36731 9.76914 5.82766 8.11625 7.6854 7.09964L6.22308 5.63732ZM9.47955 8.89379C8.5768 9.6272 7.99997 10.7462 7.99997 12C7.99997 14.2091 9.79083 16 12 16C13.2537 16 14.3728 15.4232 15.1062 14.5204L13.6766 13.0908C13.3197 13.6382 12.7021 14 12 14C10.8954 14 9.99997 13.1046 9.99997 12C9.99997 11.2979 10.3618 10.6802 10.9091 10.3234L9.47955 8.89379ZM15.9627 12.5485L11.4515 8.03729C11.6308 8.0127 11.8139 8 12 8C14.2091 8 16 9.79086 16 12C16 12.1861 15.9873 12.3692 15.9627 12.5485ZM18.5678 15.1536C19.3538 14.3151 19.9812 13.3259 20.4018 12.2337C20.4597 12.0835 20.4597 11.9165 20.4018 11.7663C19.1021 8.39172 15.8291 6 12 6C11.2082 6 10.4402 6.10226 9.70851 6.29433L8.11855 4.70437C9.32541 4.24913 10.6335 4 12 4C16.6835 4 20.681 6.92668 22.2682 11.0474C22.5043 11.6604 22.5043 12.3396 22.2682 12.9526C21.7464 14.3074 20.964 15.5331 19.9824 16.5682L18.5678 15.1536Z" fill="currentColor"/>
                      </svg>
                  </button>
                </div>
              `;
            } else {
              inputHtmlPls = `<div class="mt-2">${inputHtmlPls}</div>`;
            }
        
            const currentStatusPls = valuePls ? '<span class="text-green-600 font-medium">● Set</span>' : '<span class="text-gray-400">○ Not set</span>';
            divPls.innerHTML = `
              <label class="block text-sm font-medium leading-6 text-gray-900">${labelPls} <span class="float-right text-xs font-normal">${currentStatusPls}</span></label>
              ${inputHtmlPls}
            `;
            fieldsContainerPls.appendChild(divPls);
        };
      
        if (namePls === 'facebook') {
          addFieldPls('Page ID', 'page_id', 'text', dataPls.page_id);
          addFieldPls('Page Access Token', 'page_access_token', 'password', dataPls.decrypted.page_access_token, true);
        } else if (namePls === 'instagram') {
          addFieldPls('IG Business Page ID', 'page_id', 'text', dataPls.page_id);
          addFieldPls('Long-Lived User Token', 'll_user_access_token', 'password', dataPls.decrypted.ll_user_access_token, true);
        } else if (namePls === 'threads') {
          addFieldPls('Threads User ID', 'threads_user_id', 'text', dataPls.threads_user_id);
          addFieldPls('Threads Username', 'threads_username', 'text', dataPls.threads_username);
          addFieldPls('Threads Token', 'threads_long_lived_token', 'password', dataPls.decrypted.threads_long_lived_token, true);
        } else if (namePls === 'x') {
          const xFieldsPls = [
            { label: 'Consumer Key', id: 'consumer_key', value: dataPls.decrypted.consumer_key },
            { label: 'Consumer Secret', id: 'consumer_secret', value: dataPls.decrypted.consumer_secret },
            { label: 'Access Token', id: 'access_token', value: dataPls.decrypted.access_token },
            { label: 'Token Secret', id: 'access_token_secret', value: dataPls.decrypted.access_token_secret },
            { label: 'Bearer Token (Optional)', id: 'bearer_token', value: dataPls.decrypted.bearer_token }
          ];
          xFieldsPls.forEach(fPls => addFieldPls(fPls.label, fPls.id, 'password', fPls.value, true));
        }
      
        document.getElementById('editModalPls').classList.remove('hidden');
        // Hide previous messages
        const msgPls = document.getElementById('messagePls');
        msgPls.classList.add('hidden');
        msgPls.textContent = '';
        
    } catch(e) {
        console.error(e);
    } finally {
        // Restore button
        btnElementPls.innerHTML = originalTextPls;
        btnElementPls.disabled = false;
    }
}

function togglePasswordPls(btnPls) {
  const inputContainerPls = btnPls.parentElement;
  const inputPls = inputContainerPls.querySelector('input');
  const eyeOpenPls = btnPls.querySelector('.eye-open-pls');
  const eyeSlashPls = btnPls.querySelector('.eye-slash-pls');

  if (inputPls.type === 'password') {
    inputPls.type = 'text';
    eyeOpenPls.classList.add('hidden');
    eyeSlashPls.classList.remove('hidden');
  } else {
    inputPls.type = 'password';
    eyeOpenPls.classList.remove('hidden');
    eyeSlashPls.classList.add('hidden');
  }
}

document.getElementById('cancelBtnPls').onclick = () => {
  document.getElementById('editModalPls').classList.add('hidden');
};

document.getElementById('editFormPls').onsubmit = async (ePls) => {
  ePls.preventDefault();
  
  const saveBtnPls = document.getElementById('saveBtnPls');
  const btnTextPls = saveBtnPls.querySelector('.btn-text-pls');
  const spinnerPls = saveBtnPls.querySelector('.spinner-pls');

  saveBtnPls.disabled = true;
  btnTextPls.textContent = 'Saving...';
  spinnerPls.classList.remove('hidden');
  const formDataPls = {
    is_active: document.getElementById('isActivePls').checked,
    expires_at: document.getElementById('expiresAtPls').value || null,
  };

  if (currentPlatformPls === 'facebook') {
    formDataPls.page_id = document.getElementById('page_idPls')?.value || null;
    const tokenPls = document.getElementById('page_access_tokenPls').value;
    if (tokenPls) formDataPls.page_access_token = tokenPls;
  } else if (currentPlatformPls === 'instagram') {
    formDataPls.page_id = document.getElementById('page_idPls')?.value || null;
    const tokenPls = document.getElementById('ll_user_access_tokenPls').value;
    if (tokenPls) formDataPls.ll_user_access_token = tokenPls;
  } else if (currentPlatformPls === 'threads') {
    formDataPls.threads_user_id = document.getElementById('threads_user_idPls')?.value || null;
    formDataPls.threads_username = document.getElementById('threads_usernamePls')?.value || null;
    const tokenPls = document.getElementById('threads_long_lived_tokenPls').value;
    if (tokenPls) formDataPls.threads_long_lived_token = tokenPls;
  } else if (currentPlatformPls === 'x') {
    ['consumer_key', 'consumer_secret', 'access_token', 'access_token_secret', 'bearer_token'].forEach(kPls => {
      const valPls = document.getElementById(kPls + 'Pls')?.value;
      if (valPls) formDataPls[kPls] = valPls;
    });
  }

  try {
    const resPls = await fetch(`${apiBasePls}/${currentPlatformPls}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formDataPls)
    });
    const resultPls = await resPls.json();
    const msgPls = document.getElementById('messagePls');
    
    msgPls.textContent = resultPls.message || 'Configuration saved successfully.';
    msgPls.className = 'mx-6 mb-6 p-4 rounded-2xl bg-gray-100 text-gray-900 border-l-4 border-black block text-sm';
    
    loadPlatformsPls();
    setTimeout(() => {
         document.getElementById('editModalPls').classList.add('hidden');
    }, 1500);

  } catch (errPls) {
    const msgPls = document.getElementById('messagePls');
    msgPls.textContent = 'Error saving configuration.';
    msgPls.className = 'mx-6 mb-6 p-4 rounded-2xl bg-red-50 text-red-900 border-l-4 border-red-900 block text-sm';
  } finally {
    saveBtnPls.disabled = false;
    btnTextPls.textContent = 'Save Changes';
    spinnerPls.classList.add('hidden');
  }
};
String.prototype.capitalize = function() {
  return this.charAt(0).toUpperCase() + this.slice(1);
};
loadPlatformsPls();
