const formYtb = document.getElementById('downloadFormYtb');
const urlInputYtb = document.getElementById('urlYtb');
const qualitySelectYtb = document.getElementById('qualityYtb');
const audioOnlyCheckboxYtb = document.getElementById('audioOnlyYtb');
const submitBtnYtb = document.getElementById('submitBtnYtb');
const statusDivYtb = document.getElementById('statusYtb');
const downloadLinkDivYtb = document.getElementById('downloadLinkYtb');

const API_URL_Ytb = '/download'; 

const setDwnLoading = (isLoading) => {
  if (isLoading) {
    submitBtnYtb.disabled = true;
    submitBtnYtb.innerHTML = '<i class="ph ph-spinner animate-spin text-lg"></i><span>Processing...</span>';
    submitBtnYtb.classList.add('opacity-75');
    submitBtnYtb.style.cursor = 'not-allowed'; // ← This will always work
  } else {
    submitBtnYtb.disabled = false;
    submitBtnYtb.innerHTML = '<i class="ph ph-download-simple text-lg"></i><span>Download</span>';
    submitBtnYtb.classList.remove('opacity-75');
    submitBtnYtb.style.cursor = '';
  }
};
formYtb.addEventListener('submit', async (e) => {
  e.preventDefault();

  const urlYtb = urlInputYtb.value.trim();
  const qualityYtb = qualitySelectYtb.value;
  const audioOnlyYtb = audioOnlyCheckboxYtb.checked;

  if (!urlYtb) return;

  // UI: Loading state
  setDwnLoading(true);
  statusDivYtb.className = 'bg-blue-50 text-blue-700 border border-blue-100 p-4 rounded-xl text-center text-sm font-medium';
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

    if (responseYtb.ok) {
      statusDivYtb.className = 'bg-emerald-50 text-emerald-700 border border-emerald-100 p-4 rounded-xl text-center text-sm font-medium';
      statusDivYtb.textContent = `Success! Video found on ${dataYtb.platform || 'Platform'}`;
      
      downloadLinkDivYtb.innerHTML = `
      <a href="${dataYtb.download_url}" download
        class="group relative flex items-center justify-center gap-4 px-5 py-2 
                font-semibold text-sm text-white
                bg-neutral-900 border border-neutral-800
                rounded-full shadow-xl
                transition-all duration-400 ease-out
                hover:bg-neutral-800 hover:border-gray-500/50 hover:shadow-2xl hover:shadow-gray-500/20
                hover:-translate-y-[2px] active:translate-y-0">

        <span class="text-xl transition-transform group-hover:scale-110">
          <i class="ph-bold ph-download-simple"></i>
        </span>

        <span class="tracking-tight">
          Save ${audioOnlyYtb ? 'Audio' : 'Video'} to Device
        </span>

        <!-- Subtle shine -->
        <span class="absolute inset-0 rounded-2xl bg-gradient-to-r from-transparent via-white/10 to-transparent 
                      -translate-x-full group-hover:translate-x-full transition-transform duration-1000"></span>
      </a>
    `;
    } else {
      throw new Error(dataYtb.detail || 'Download failed');
    }
  } catch (errorYtb) {
    statusDivYtb.className = 'bg-red-50 text-red-700 border border-red-100 p-4 rounded-xl text-center text-sm font-medium';
    statusDivYtb.textContent = `Error: ${errorYtb.message}`;
  } finally {
    setDwnLoading(false);
  }
});