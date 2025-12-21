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

const options = [
    { value: 'product_overview', label: 'Product Overview', icon: 'package' },
    { value: 'technical_specifications', label: 'Technical Specs', icon: 'cpu' },
    { value: 'warranty_and_return_policy', label: 'Warranty & Policy', icon: 'shield-check' },
    { value: 'product_images', label: 'Product Images', icon: 'image' },
    { value: 'faqs', label: 'FAQs', icon: 'help-circle' }, // Note: help-circle is standard in many versions
    { value: 'related_products_alternatives', label: 'Related Products', icon: 'layers' },
    { value: 'customer_ratings_reviews_summary', label: 'Customer Reviews', icon: 'star' },
    { value: 'expert_third_party_reviews', label: 'Expert Reviews', icon: 'award' },
  ];

  // 2. Element Selection
  const trigger = document.getElementById('dropdown-trigger');
  const menu = document.getElementById('dropdown-menu');
  const chevronFr = document.getElementById('chevronFr');
  const selectedIconContainer = document.getElementById('selected-icon-container');
  const selectedLabel = document.getElementById('selected-labelFr');
  const menuList = document.getElementById('menu-listFr');

  let currentValue = 'product_overview';

  function renderMenu() {
    menuList.innerHTML = ''; 
    
    options.forEach(option => {
      const li = document.createElement('li');
      const button = document.createElement('button');

      let baseClasses = 'w-full flex items-center gap-2 px-2 py-2 rounded-xl text-left transition-all duration-200 group ';
      if (option.value === currentValue) {
        button.className = baseClasses + 'bg-black text-white shadow-md';
      } else {
        button.className = baseClasses + 'text-gray-600 hover:bg-gray-100 hover:text-black';
      }

      button.type = 'button';

      const checkmark = option.value === currentValue 
          ? `<div class="ml-auto"><i data-lucide="check" class="w-4 h-4"></i></div>` 
          : '';

      button.innerHTML = `
        <i data-lucide="${option.icon}" class="w-5 h-5 transition-colors"></i>
        <span class="font-medium">${option.label}</span>
        ${checkmark}
      `;

      button.addEventListener('click', () => {
        handleSelect(option);
      });

      li.appendChild(button);
      menuList.appendChild(li);
    });

    lucide.createIcons();
  }
  function handleSelect(option) {
    currentValue = option.value;
    selectedLabel.textContent = option.label;
    selectedIconContainer.innerHTML = `<i data-lucide="${option.icon}" class="w-6 h-6"></i>`;
    lucide.createIcons();
    toggleMenu(false);
    renderMenu();
  }
  function toggleMenu(show) {
    if (show) {
      menu.classList.remove('hidden');
      setTimeout(() => {
          menu.classList.remove('opacity-0', 'scale-95');
          menu.classList.add('opacity-100', 'scale-100');
      }, 10);
      chevronFr.classList.add('rotate-180');
    } else {
      menu.classList.remove('opacity-100', 'scale-100');
      menu.classList.add('opacity-0', 'scale-95');
      chevronFr.classList.remove('rotate-180');
      setTimeout(() => {
          menu.classList.add('hidden');
      }, 200);
    }
  }

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    const isHidden = menu.classList.contains('hidden');
    toggleMenu(isHidden);
  });

  document.addEventListener('click', () => {
    if (!menu.classList.contains('hidden')) {
      toggleMenu(false);
    }
  });

  menu.addEventListener('click', (e) => {
    e.stopPropagation();
  });
  const initialOption = options[0];
  selectedIconContainer.innerHTML = `<i data-lucide="${initialOption.icon}" class="w-6 h-6"></i>`;
  renderMenu();
  lucide.createIcons();


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

const observer = new MutationObserver(() => {
    document.querySelectorAll('#reviewsDisplayRes img:not([data-error-handled])').forEach(img => {
        img.addEventListener('error', function() { this.remove(); });
        img.dataset.errorHandled = 'true';
    });
});


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
        clarification: clarification,
        sys_promt:currentValue
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

        if (contentType && contentType.includes('application/json')) {
            try {
                const clarificationData = await responseRes.json();
                console.log('Clarification data:', clarificationData);
                
                if (clarificationData.needs_clarification && clarificationData.question) {
                    loadingIndicatorRes.classList.add('hidden');
                    clarificationQuestion.textContent = clarificationData.question;
                    clarificationInput.value = '';
                    clarificationContainer.classList.remove('hidden');
                    clarificationInput.focus();
                    return;
                } else if (clarificationData.error || clarificationData.detail) {
                    throw new Error(clarificationData.error || clarificationData.detail || 'Unknown error');
                } else {
                    console.error('Unexpected JSON structure:', clarificationData);
                    throw new Error('Could not process the request. Please try again.');
                }
            } catch (jsonError) {
                console.error('JSON parsing error:', jsonError);
                throw new Error('Invalid response from server. Please try again.');
            }
        }

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
        observer.observe(document.getElementById('reviewsDisplayRes'), { childList: true, subtree: true });

        // Handle streaming response
        loadingIndicatorRes.classList.add('hidden');
        resultsContainer.classList.remove('hidden');
        Rescursor.classList.remove('hidden'); 

        const readerRes = responseRes.body.getReader();
        const decoderRes = new TextDecoder();
        let fullTextBuffer = '';

        while (true) {
            const { done, value } = await readerRes.read();
            if (done) break;

            const chunk = decoderRes.decode(value, { stream: true });
            fullTextBuffer += chunk;

            // First: parse Markdown (safe now – no raw images)
            let html = marked.parse(fullTextBuffer);

            // Then: replace custom <product-images> tag with styled image gallery
            html = html.replace(
                /<product-images>(.*?)<\/product-images>/gis,
                (match, urlsBlock) => {
                    const urls = urlsBlock
                        .trim()
                        .split('\n')
                        .filter(url => url.trim().length > 0);

                    if (urls.length === 0) return '<p>No images available.</p>';

                    // Create responsive, centered image grid
                    const imagesHtml = urls
                        .map(url => `
                                <div class="product-image-wrapper">
                                    <img src="${url.trim()}" alt="Product image" loading="lazy">
                                </div>
                        `)
                        .join('');

                    return `
                        <div class="product-images-gallery">
                            ${imagesHtml}
                        </div>
                    `;
                }
            );

            reviewsDisplayRes.innerHTML = html;
            reviewsDisplayRes.scrollTop = reviewsDisplayRes.scrollHeight;
        }

        // Final render after stream ends
        if (fullTextBuffer.trim()) {
            let finalHtml = marked.parse(fullTextBuffer);
            finalHtml = finalHtml.replace(
                /<product-images>(.*?)<\/product-images>/gis,
                (match, urlsBlock) => {
                    const urls = urlsBlock.trim().split('\n').filter(Boolean);
                    if (urls.length === 0) return '<p>No images available.</p>';

                    const imagesHtml = urls
                        .map(url => `
                            <div class="product-image-wrapper">
                                <img src="${url.trim()}" alt="Product image" loading="lazy">
                            </div>
                        `)
                        .join('');

                    return `<div class="product-images-gallery"><div class="gallery-inner">${imagesHtml}</div></div>`;
                }
            );

            reviewsDisplayRes.innerHTML = finalHtml;
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