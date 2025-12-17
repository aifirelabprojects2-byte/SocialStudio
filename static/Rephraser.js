const fetchFormRfx = document.getElementById('fetchFormRfx');
const createFormRfx = document.getElementById('createFormRfx');
const fetchedDetailsRfx = document.getElementById('fetchedDetailsRfx');
const skeletonLoaderRfx = document.getElementById('skeletonLoaderRfx');
const statusRfx = document.getElementById('statusRfx');
const processAnimationRfx = document.getElementById('processAnimationRfx');
const shimmerTextRfx = document.getElementById('shimmerTextRfx');
const createSubmitBtnRfx = document.getElementById('createSubmitBtnRfx');

const fetchedHeaderBtn = document.getElementById('fetchedHeaderBtn');
const fetchedContentBody = document.getElementById('fetchedContentBody');
const fetchedChevron = document.getElementById('fetchedChevron');



fetchedHeaderBtn.addEventListener('click', () => {
    const isHidden = fetchedContentBody.classList.contains('hidden');
    if (isHidden) {
        fetchedContentBody.classList.remove('hidden');
        fetchedChevron.classList.add('rotate-180');
    } else {
        fetchedContentBody.classList.add('hidden');
        fetchedChevron.classList.remove('rotate-180');
    }
});

// Helper to force open state
function openFetchedContent() {
    fetchedContentBody.classList.remove('hidden');
    fetchedChevron.classList.add('rotate-180');
}

let animationIntervalRfx;
const animationPhrasesRfx = [
    "Analyzing aesthetics...",
    "Evaluating layout balance...",
    "Enhancing visual harmony...",
    "Constructing composition...",
    "Refining color palette...",
    "Polishing pixels...",
    "Optimizing typography...",
    "Rephrasing content...",
    "Applying themes...",
    "Adding final touches...",
    "Preparing masterpiece...",
    "Finalizing edits..."
];

function startShimmerAnimationRfx() {

    processAnimationRfx.classList.remove('hidden');

    let index = 0;
    shimmerTextRfx.innerText = animationPhrasesRfx[0];

    animationIntervalRfx = setInterval(() => {
        index++;

        if (index >= animationPhrasesRfx.length) {
            clearInterval(animationIntervalRfx);
            shimmerTextRfx.style.opacity = '1';
            shimmerTextRfx.innerText = animationPhrasesRfx[animationPhrasesRfx.length - 1];
            return;
        }
        shimmerTextRfx.style.opacity = '0.5';
        setTimeout(() => {
            shimmerTextRfx.innerText = animationPhrasesRfx[index];
            shimmerTextRfx.style.opacity = '1';
        }, 200);
    }, 1800); 
}

function stopShimmerAnimationRfx() {
    clearInterval(animationIntervalRfx);
    processAnimationRfx.classList.add('hidden');
}

// --- Load Themes ---
async function loadThemesRfx() {
    try {
        const response = await fetch(`/api/themes`);
        if (!response.ok) throw new Error('Failed to fetch themes');
        const themes = await response.json();
        
        const select = document.getElementById('theme_idRfx');
        select.innerHTML = '<option value="">Select a theme</option>';
        themes.forEach(theme => {
            const option = document.createElement('option');
            option.value = theme.theme_id; 
            option.textContent = `${theme.name} - ${theme.description}`;
            select.appendChild(option);
        });
    } catch (error) {
        statusRfx.innerHTML = `<p class="text-red-600 bg-red-50 p-3 rounded-2xl border border-red-200 text-sm flex items-center"><svg class="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>Failed to load themes: ${error.message}</p>`;
    }
}

loadThemesRfx();

// --- Fetch Post Logic ---
fetchFormRfx.addEventListener('submit', async (e) => {
    e.preventDefault();
    const urlVal = document.getElementById('urlRfx').value.trim();

    const fetchBtn = document.getElementById('fetchBtnRfx');
    const fetchBtnText = document.getElementById('fetchBtnTextRfx');
    const fetchBtnSpinner = document.getElementById('fetchBtnSpinnerRfx');

    // UI States
    fetchBtn.disabled = true;
    fetchBtn.classList.add('opacity-75', 'cursor-not-allowed');
    fetchBtnText.classList.add('hidden');
    fetchBtnSpinner.classList.remove('hidden');

    statusRfx.innerHTML = '';
    fetchedDetailsRfx.classList.add('hidden'); 
    skeletonLoaderRfx.classList.remove('hidden'); 

    try {
        const response = await fetch(`/api/fetch-post-details`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: urlVal }) 
        });
        const data = await response.json();

        // Hide skeleton
        skeletonLoaderRfx.classList.add('hidden');

        if (response.ok) {
            const captionHtml = `<p class="whitespace-pre-wrap leading-relaxed">${data.caption ? data.caption : 'No caption'}</p>`;
            document.getElementById('captionRfx').innerHTML = captionHtml;

            // Update Media
            let mediaHtml = '';
            if (data.media_urls && data.media_urls.length > 0) {
                data.media_urls.forEach((url, index) => {
                    const ext = url.split('.').pop().toLowerCase();
                    if (['mp4', 'mov', 'avi'].includes(ext)) {
                        mediaHtml += `
                            <video controls class="w-full h-auto rounded-lg shadow-sm">
                                <source src="${url}" type="video/mp4">
                                Your browser does not support video.
                            </video>`;
                    } else {
                        mediaHtml += `
                            <img src="${url}" alt="Post media ${index + 1}" class="w-full h-auto rounded-lg shadow-sm object-cover"
                                onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                            <div class="hidden text-center p-4 text-gray-400 bg-gray-100 rounded-lg">
                                <span class="block text-2xl mb-2">⚠️</span>
                                Image failed to load
                            </div>`;
                    }
                });
            } else {
                mediaHtml = '<div class="p-8 text-center text-gray-400 bg-gray-50 rounded-lg w-full"><p class="italic">No media found.</p></div>';
            }
            document.getElementById('mediaRfx').innerHTML = mediaHtml;

            // Store Hidden Data
            document.getElementById('fetched_captionRfx').value = data.caption || '';

            // Image Logic
            let imgpath = '';
            if (data.media_urls && data.media_urls.length > 0) {
                const firstImage = data.media_urls.find(url => {
                    const ext = url.split('.').pop().toLowerCase();
                    return !['mp4', 'mov', 'avi'].includes(ext);
                });
                imgpath = firstImage || data.media_urls[0];
            }
            document.getElementById('fetched_imgpathRfx').value = imgpath;

            // Show Results Section
            fetchedDetailsRfx.classList.remove('hidden');
            openFetchedContent(); // Ensure it's expanded
            createSubmitBtnRfx.disabled = false;

        } else {
            statusRfx.innerHTML = `<p class="text-red-600 bg-red-50 p-4 rounded-2xl border border-red-200 text-sm">Error: ${data.detail || 'Unknown error'}</p>`;
        }
    } catch (error) {
        skeletonLoaderRfx.classList.add('hidden');
        statusRfx.innerHTML = `<p class="text-red-600 bg-red-50 p-4 rounded-2xl border border-red-200 text-sm">Fetch error: ${error.message}</p>`;
    }
    finally {
        fetchBtn.disabled = false;
        fetchBtn.classList.remove('opacity-75', 'cursor-not-allowed');
        fetchBtnText.classList.remove('hidden');
        fetchBtnSpinner.classList.add('hidden');
    }
});

// --- Create Task Logic ---
createFormRfx.addEventListener('submit', async (e) => {
    e.preventDefault();

    const captionVal = document.getElementById('fetched_captionRfx').value;
    const imgpathVal = document.getElementById('fetched_imgpathRfx').value;
    const rephrase_promptVal = document.getElementById('rephrase_promptRfx').value.trim();
    const image_suggestionVal = document.getElementById('image_suggestionRfx').value.trim();
    const theme_idVal = document.getElementById('theme_idRfx').value;
    const modelVal = document.getElementById('modelRfx').value;

    if (!imgpathVal) {
        statusRfx.innerHTML = '<p class="text-red-600 bg-red-50 p-3 rounded-2xl border border-red-200 text-sm">No image found in the post. Cannot proceed.</p>';
        return;
    }

    if (!theme_idVal) {
        statusRfx.innerHTML = '<p class="text-red-600 bg-red-50 p-3 rounded-2xl border border-red-200 text-sm">Please select a theme.</p>';
        return;
    }

    // Lock UI
    createSubmitBtnRfx.disabled = true;
    statusRfx.innerHTML = '';
    
    // KEY REQUEST LOGIC: Hide fetched content container during animation
    fetchedDetailsRfx.classList.add('hidden');
    
    // Start Animation
    startShimmerAnimationRfx();

    try {
        // Backend API call
        const response = await fetch(`/api/create-draft-task`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rephrase_prompt: rephrase_promptVal,
                image_suggestion: image_suggestionVal,
                theme_id: theme_idVal,
                model: modelVal,
                imgpath: imgpathVal,
                caption: captionVal
            })
        });
        const data = await response.json();

        stopShimmerAnimationRfx();

        if (response.ok) {
            statusRfx.innerHTML = `
                <div class="bg-green-50 border border-green-200 rounded-2xl p-5 flex items-start space-x-3 shadow-sm">
                    <svg class="h-6 w-6 text-green-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                        <h3 class="text-sm font-semibold text-green-800">Task Created Successfully!</h3>
                        <p class="text-sm text-green-700 mt-1">Task ID: <span class="font-mono bg-green-100 px-1 rounded">${data.task_id}</span></p>
                        <p class="text-sm text-green-700 mt-1">${data.message}</p>
                    </div>
                </div>
            `;
            createFormRfx.reset();
            // Keep fetchedDetailsRfx hidden (as previously requested)
            // Reset hidden fields
            document.getElementById('fetched_captionRfx').value = '';
            document.getElementById('fetched_imgpathRfx').value = '';
            
        } else {
            // Show Content again on Error
            fetchedDetailsRfx.classList.remove('hidden');
            openFetchedContent();
            statusRfx.innerHTML = `<p class="text-red-600 bg-red-50 p-4 rounded-2xl border border-red-200 text-sm">Error: ${data.detail || 'Unknown error'}</p>`;
            createSubmitBtnRfx.disabled = false;
        }
    } catch (error) {
        stopShimmerAnimationRfx();
        fetchedDetailsRfx.classList.remove('hidden'); 
        openFetchedContent();
        statusRfx.innerHTML = `<p class="text-red-600 bg-red-50 p-4 rounded-2xl border border-red-200 text-sm">Create error: ${error.message}</p>`;
        createSubmitBtnRfx.disabled = false;
    }
});