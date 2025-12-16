const formRes = document.getElementById('reviewFormRes');
const inputRes = document.getElementById('productCompanyInputRes');
const submitButtonRes = document.getElementById('submitButtonRes');
const loadingIndicatorRes = document.getElementById('loadingIndicatorRes');
const errorMessageRes = document.getElementById('errorMessageRes');
const reviewsDisplayRes = document.getElementById('reviewsDisplayRes');
const resultsContainer = document.getElementById('resultsContainer');
const Rescursor = document.getElementById('Rescursor');

const deepSearchToggle = document.getElementById('deepSearchToggle');
const customFilterToggle = document.getElementById('customFilterToggle');
const customFilterContainer = document.getElementById('customFilterContainer');
const customFilterInput = document.getElementById('customFilterInput');

const clarificationContainer = document.getElementById('clarificationContainer');
const clarificationQuestion = document.getElementById('clarificationQuestion');
const clarificationInput = document.getElementById('clarificationInput');
const clarificationSubmit = document.getElementById('clarificationSubmit');

customFilterToggle.addEventListener('click', () => {
    customFilterContainer.classList.toggle('hidden');
    if (!customFilterContainer.classList.contains('hidden')) {
        customFilterInput.focus();
    }
});

marked.use({
    breaks: true, 
    gfm: true    
});

let currentPayload = null;

async function handleSubmitRes(event, isClarification = false) {
    event?.preventDefault();
    const productCompanyRes = inputRes.value.trim();

    const isDeepResearch = deepSearchToggle.checked;
    const customFilter = customFilterInput.value.trim() || null;
    const clarification = isClarification ? clarificationInput.value.trim() : null;

    if (!productCompanyRes) return;

    // Reset UI
    reviewsDisplayRes.innerHTML = '';
    resultsContainer.classList.add('hidden');
    errorMessageRes.classList.add('hidden');
    clarificationContainer.classList.add('hidden');
    loadingIndicatorRes.classList.remove('hidden');

    const originalBtnContent = submitButtonRes.innerHTML;
    submitButtonRes.disabled = true;
    submitButtonRes.innerHTML = `<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Processing...`;
    submitButtonRes.style.cursor = 'not-allowed'; 
    let fullTextBuffer = '';

    const payload = { 
        product_company: productCompanyRes,
        is_deepresearch_needed: isDeepResearch,
        custom_filter: customFilter,
        clarification: clarification
    };
    currentPayload = payload;

    try {
        const responseRes = await fetch('/reviews', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        console.log('Response status:', responseRes.status);

        const contentType = responseRes.headers.get('content-type');

        // Handle JSON responses (clarification needed)
        if (contentType && contentType.includes('application/json')) {
            try {
                const clarificationData = await responseRes.json();
                console.log('Clarification data:', clarificationData);
                
                if (clarificationData.needs_clarification && clarificationData.question) {
                    // Show clarification UI
                    loadingIndicatorRes.classList.add('hidden');
                    clarificationQuestion.textContent = clarificationData.question;
                    clarificationInput.value = '';
                    clarificationContainer.classList.remove('hidden');
                    clarificationInput.focus();
                    return;
                } else if (clarificationData.error || clarificationData.detail) {
                    // Handle error responses
                    throw new Error(clarificationData.error || clarificationData.detail || 'Unknown error');
                } else {
                    // Unexpected JSON structure
                    console.error('Unexpected JSON structure:', clarificationData);
                    throw new Error('Could not process the request. Please try again.');
                }
            } catch (jsonError) {
                console.error('JSON parsing error:', jsonError);
                throw new Error('Invalid response from server. Please try again.');
            }
        }

        // Handle error status codes
        if (!responseRes.ok) {
            let errorMessage = 'Request failed';
            try {
                const errorDataRes = await responseRes.json();
                errorMessage = errorDataRes.detail || errorMessage;
            } catch {
                errorMessage = `Server error (${responseRes.status})`;
            }
            throw new Error(errorMessage);
        }

        // Handle streaming response
        loadingIndicatorRes.classList.add('hidden');
        resultsContainer.classList.remove('hidden');
        Rescursor.classList.remove('hidden'); 

        const readerRes = responseRes.body.getReader();
        const decoderRes = new TextDecoder();

        while (true) {
            const { done, value } = await readerRes.read();
            if (done) break;

            const chunk = decoderRes.decode(value, { stream: true });
            fullTextBuffer += chunk;

            reviewsDisplayRes.innerHTML = marked.parse(fullTextBuffer);
            reviewsDisplayRes.scrollTop = reviewsDisplayRes.scrollHeight;
        }

        if (fullTextBuffer.trim()) {
            reviewsDisplayRes.innerHTML = marked.parse(fullTextBuffer);
        } else {
            throw new Error('No content received from server');
        }

    } catch (errorRes) {
        console.error('Request error:', errorRes);
        errorMessageRes.textContent = errorRes.message || 'An error occurred while fetching reviews.';
        errorMessageRes.classList.remove('hidden');
        loadingIndicatorRes.classList.add('hidden');
    } finally {
        submitButtonRes.disabled = false;
        submitButtonRes.style.cursor = ''; 
        submitButtonRes.innerHTML = originalBtnContent;
        Rescursor.classList.add('hidden'); 
    }
}

clarificationSubmit.addEventListener('click', (e) => {
    if (clarificationInput.value.trim()) {
        handleSubmitRes(e, true); 
    }
});

// Allow Enter key in clarification input
clarificationInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && clarificationInput.value.trim()) {
        handleSubmitRes(e, true);
    }
});

formRes.addEventListener('submit', (e) => handleSubmitRes(e, false));

function copyToClipboard() {
    const text = reviewsDisplayRes.innerText;
    navigator.clipboard.writeText(text).then(() => {
        ShowNoti('info', 'copied to clipboard');
    });
}