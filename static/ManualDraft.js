const createBtnMnl = document.getElementById('createBtnMnl');
const modalOverlayMnl = document.getElementById('modalOverlayMnl');
const modalContentMnl = document.getElementById('modalContentMnl');
const closeBtnMnl = document.getElementById('closeBtnMnl');
const manualFormMnl = document.getElementById('manualFormMnl');
const submitBtnMnl = document.getElementById('submitBtnMnl');
const progressContainerMnl = document.getElementById('progressContainerMnl');
const progressBarMnl = document.getElementById('progressBarMnl');
const progressTextMnl = document.getElementById('progressTextMnl');
const imageInputMnl = document.getElementById('imageMnl');
const fileNameMnl = document.getElementById('fileNameMnl');

// File input styling helper
imageInputMnl.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        fileNameMnl.textContent = e.target.files[0].name;
        fileNameMnl.classList.add('text-gray-800');
        fileNameMnl.classList.remove('text-gray-600');
    } else {
        fileNameMnl.textContent = "Select image file...";
        fileNameMnl.classList.remove('text-gray-800');
        fileNameMnl.classList.add('text-gray-600');
    }
});

// Open modal
createBtnMnl.addEventListener('click', () => {
    modalOverlayMnl.classList.remove('hidden');
    setTimeout(() => {
        modalOverlayMnl.classList.remove('opacity-0');
        modalContentMnl.classList.remove('scale-95');
        modalContentMnl.classList.add('scale-100');
    }, 10);
    document.body.style.overflow = 'hidden';
});

// Close modal function
function closeModalMnl() {
    modalOverlayMnl.classList.add('opacity-0');
    modalContentMnl.classList.remove('scale-100');
    modalContentMnl.classList.add('scale-95');
    
    setTimeout(() => {
        modalOverlayMnl.classList.add('hidden');
        document.body.style.overflow = 'auto';
        resetFormMnl();
    }, 300); 
}

closeBtnMnl.addEventListener('click', closeModalMnl);
modalOverlayMnl.addEventListener('click', (e) => {
    if (e.target === modalOverlayMnl) closeModalMnl();
});

function resetFormMnl() {
    manualFormMnl.reset();
    fileNameMnl.textContent = "Select image file...";
    fileNameMnl.classList.remove('text-gray-800');
    fileNameMnl.classList.add('text-gray-600');
    
    progressContainerMnl.classList.add('hidden');
    progressBarMnl.style.width = '0%';
    progressTextMnl.textContent = '0%';

    submitBtnMnl.disabled = false;
    submitBtnMnl.innerHTML = `<span>Create Post</span>`;
    submitBtnMnl.classList.remove('opacity-50', 'cursor-not-allowed');
}

manualFormMnl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formDataMnl = new FormData(manualFormMnl);
    const scheduledAtElMnl = document.getElementById('scheduled_atMnl');
    if (scheduledAtElMnl) {
        const scheduledAtValMnl = scheduledAtElMnl.value;
        if (scheduledAtValMnl) {
            const dateMnl = new Date(scheduledAtValMnl);
            formDataMnl.set('scheduled_at', dateMnl.toISOString());
        }
    }

    const xhrMnl = new XMLHttpRequest();
    xhrMnl.open('POST', '/manual-tasks', true);

    // Track progress
    xhrMnl.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percentCompleteMnl = (e.loaded / e.total) * 100;
            progressBarMnl.style.width = percentCompleteMnl + '%';
            progressTextMnl.textContent = Math.round(percentCompleteMnl) + '%';
        }
    });

    xhrMnl.addEventListener('load', () => {
        if (xhrMnl.status === 200) {
            let responseMnl;
            try {
                responseMnl = JSON.parse(xhrMnl.responseText);
            } catch(err) {
                responseMnl = { task_id: 'Unknown', img_url: 'Unknown' };
            }
            
            submitBtnMnl.textContent = 'Post Created!';
            submitBtnMnl.disabled = true;
            submitBtnMnl.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
            submitBtnMnl.disabled = false;
            submitBtnMnl.innerHTML = `<span>Try Again</span>`;
        }
        progressContainerMnl.classList.add('hidden');
    });

    xhrMnl.addEventListener('error', () => {
        progressContainerMnl.classList.add('hidden');
        submitBtnMnl.disabled = false;
        submitBtnMnl.textContent = 'Try Again';
    });

    // Show progress and update UI
    progressContainerMnl.classList.remove('hidden');
    progressBarMnl.style.width = '0%';
    progressTextMnl.textContent = '0%';
    submitBtnMnl.disabled = true;
    submitBtnMnl.innerHTML = `<span>Uploading...</span>`;

    xhrMnl.send(formDataMnl);
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modalOverlayMnl.classList.contains('hidden')) {
        closeModalMnl();
    }
});

