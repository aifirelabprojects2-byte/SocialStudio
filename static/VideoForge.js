const clientIdVds = 'client_' + Math.random().toString(36).substr(2, 9);
let wsVds;
const formVds = document.getElementById('videoFormVds');
const fileInputVds = document.getElementById('videoFileVds');
const fileNameDisplayVds = document.getElementById('fileNameVds');
const submitBtnVds = document.getElementById('submitBtnVds');
const btnTextVds = document.getElementById('btnTextVds');
const progressSectionVds = document.getElementById('progressSectionVds');
const progressBarVds = document.getElementById('progressBarVds');
const progressPercentVds = document.getElementById('progressPercentVds');
const progressStatusVds = document.getElementById('progressStatusVds');
const resultSectionVds = document.getElementById('resultSectionVds');
const downloadLinkVds = document.getElementById('downloadLinkVds');
const logContainerVds = document.getElementById('logContainerVds');


fileInputVds.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        fileNameDisplayVds.textContent = e.target.files[0].name;
        fileNameDisplayVds.classList.add('underline');
    }
});


function connectWebSocketVds() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    wsVds = new WebSocket(`${protocol}//${window.location.host}/ws/${clientIdVds}`);

    wsVds.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'progress') {
            const percent = data.progress;
            progressBarVds.style.width = percent + '%';
            progressPercentVds.textContent = percent + '%';
            progressStatusVds.textContent = data.message;
        } else if (data.type === 'log') {
            const p = document.createElement('p');
            p.textContent = '> ' + data.message;
            p.className = "mb-1 border-b border-gray-100 pb-1 last:border-0";
            logContainerVds.appendChild(p);
            logContainerVds.scrollTop = logContainerVds.scrollHeight;
        } else if (data.type === 'status') {
            progressStatusVds.textContent = data.message;
        } else if (data.type === 'complete') {
            progressBarVds.style.width = '100%';
            progressPercentVds.textContent = '100%';
            progressStatusVds.textContent = 'Complete';
            
            // Bug Fix: Reset button animation immediately on completion
            resetButtonStateVds();

            setTimeout(() => {
                progressSectionVds.classList.add('hidden');
                resultSectionVds.classList.remove('hidden');
                downloadLinkVds.href = data.download_url;
            }, 800);
        } else if (data.type === 'error') {
            alert(data.message);
            resetUIVds();
        }
    };

    wsVds.onerror = (error) => {
        console.error("WebSocket Error:", error);
    };
}

function resetButtonStateVds() {
    submitBtnVds.disabled = false;
    btnTextVds.innerHTML = 'Generate Video <i class="fa-solid fa-arrow-right ml-2 text-sm"></i>';
    submitBtnVds.classList.remove('opacity-75', 'cursor-not-allowed');
}

function resetUIVds() {
    resetButtonStateVds();
    progressSectionVds.classList.add('hidden');
}

// Form Submit
formVds.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    if (!fileInputVds.files.length) {
        alert("Please select a video file first.");
        return;
    }

    // UI Loading State
    submitBtnVds.disabled = true;
    submitBtnVds.classList.add('opacity-75', 'cursor-not-allowed');
    // Using black spinner styling defined in CSS
    btnTextVds.innerHTML = '<div class="loading-spinner-Vds mr-3"></div> Processing...';
    
    progressSectionVds.classList.remove('hidden');
    resultSectionVds.classList.add('hidden');
    logContainerVds.innerHTML = '<p class="text-gray-400">> Connection established...</p>';
    progressBarVds.style.width = '0%';
    progressPercentVds.textContent = '0%';

    // Ensure WebSocket is connected
    if (!wsVds || wsVds.readyState !== WebSocket.OPEN) {
        connectWebSocketVds();
        // Give it a moment to connect
        await new Promise(r => setTimeout(r, 1000));
    }

    const formData = new FormData(formVds);
    formData.append('client_id', clientIdVds);

    try {
        const response = await fetch('/process-video', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }
    } catch (error) {
        console.error("Upload Error:", error);
        alert("Upload failed: " + error.message);
        resetUIVds();
    }
});

connectWebSocketVds();
