document.addEventListener('DOMContentLoaded', () => {
    
    // --- Helper: Insert Text at Cursor Position ---
    function insertTextAtCursor(text) {
        const textarea = elements.caption;
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const before = textarea.value.substring(0, start);
        const after = textarea.value.substring(end, textarea.value.length);
        
        textarea.value = before + text + after;
        textarea.selectionStart = textarea.selectionEnd = start + text.length;
        textarea.focus();
        updatePreview(); 
    }

    const hashtagBtn = document.getElementById('hashtagBtnMnl');
    hashtagBtn.addEventListener('click', () => {
        insertTextAtCursor(' #');
    });

    // --- Emoji Logic ---
    const emojiBtn = document.getElementById('emojiBtnMnl');
    const emojiPicker = document.getElementById('emojiPickerMnl');
    const emojiGrid = document.getElementById('emojiGridMnl');
    
    const commonEmojis = [
        '😀','😃','😄','😁','😆','😅','😂','🤣','🥲','☺️','😊','😇','🙂','🙃','😉','😌','😍','🥰','😘','😗',
        '😋','😛','😝','😜','🤪','🤨','🧐','🤓','😎','🥸','🤩','🥳','😏','😒','😞','😔','😟','😕','🙁','☹️',
        '😣','😖','😫','😩','🥺','😢','😭','😤','😠','😡','🤬','🤯','😳','🥵','🥶','😱','😨','😰','😥','😓',
        '🤗','🤔','🤭','🤫','🤥','😶','😐','😑','😬','🙄','😯','😦','😧','😮','😲','🥱','😴','🤤','😪','😵',
        '🤐','🥴','🤢','🤮','🤧','😷','🤒','🤕','🤑','🤠','😈','👿','👹','👺','🤡','💩','👻','💀','☠️','👽',
        '👾','🤖','🎃','😺','😸','😹','😻','😼','😽','🙀','😿','😾','👋','🤚','🖐','✋','🖖','👌','🤌','🤏',
        '✌️','🤞','🤟','🤘','🤙','👈','👉','👆','🖕','👇','👍','👎','✊','👊','🤛','🤜','👏','🙌','👐','🤲',
        '🤝','🙏','🔥','✨','🌟','❤️','🧡','💛','💚','💙','💜','🖤','🤍','💯','💢','💥','💫','💦','💨','🕳️'
    ];

    if(emojiGrid.children.length === 0) {
        commonEmojis.forEach(emoji => {
            const btn = document.createElement('button');
            btn.textContent = emoji;
            btn.className = "text-xl p-1 hover:bg-gray-100 rounded cursor-pointer transition";
            btn.onclick = (e) => {
                e.stopPropagation();
                insertTextAtCursor(emoji);
            };
            emojiGrid.appendChild(btn);
        });
    }
    emojiBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        emojiPicker.classList.toggle('hidden');
    });

    document.addEventListener('click', (e) => {
        if (!emojiPicker.contains(e.target) && !emojiBtn.contains(e.target)) {
            emojiPicker.classList.add('hidden');
        }
    });

    const elements = {
        createBtn: document.getElementById('createBtnMnl'),
        modal: document.getElementById('modalOverlayMnl'),
        content: document.getElementById('modalContentMnl'),
        closeBtn: document.getElementById('closeBtnMnl'),
        submitBtn: document.getElementById('submitBtnMnl'),
        saveAsDraftBtn: document.getElementById('saveAsDraftBtn'),
        fileInput: document.getElementById('fileInputMnl'),
        caption: document.getElementById('captionMnl'),
        preview: document.getElementById('previewMnl'),
        previewTitle: document.getElementById('preview-title'),
        platformSelector: document.getElementById('platform-selector'),
        postTypeSelector: document.getElementById('post-type-selector'),
        platformId: document.getElementById('platformIdMnl'),
        activePlatformIcon: document.getElementById('activePlatformIcon'),
        inputMediaPreview: document.getElementById('inputMediaPreview'),
        inputMediaImg: document.getElementById('inputMediaImg'),
        inputMediaVideo: document.getElementById('inputMediaVideo'),
        mediaCountOverlay: document.getElementById('mediaCountOverlay'),
        removeMediaBtn: document.getElementById('removeMediaBtn')
    };

    // --- State ---
    let state = {
        currentPlatform: null,
        currentPostType: 'Post',
        mediaItems: [], // Array of objects: { type: 'image'|'video', src: 'data:...' }
        rawFiles: [],   // Keep track of actual File objects for FormData
        platforms: []
    };


    async function loadPlatforms() {
        try {
            const response = await fetch('/api/active/platforms');
            state.platforms = await response.json();
            renderPlatformSelector();
            if (state.platforms.length > 0) selectPlatform(state.platforms[0]);
        } catch (e) {
            console.error('Failed to load platforms:', e);
            // Mock data 
            state.platforms = [
                { platform_id: 1, api_name: 'Instagram', account_name: 'pablo_dev', profile_photo_url: 'https://ui-avatars.com/api/?name=P&background=random' },
                { platform_id: 2, api_name: 'LinkedIn', account_name: 'Pablo Inc', profile_photo_url: 'https://ui-avatars.com/api/?name=L&background=0077b5&color=fff' },
                { platform_id: 3, api_name: 'Facebook', account_name: 'Pablo Social', profile_photo_url: 'https://ui-avatars.com/api/?name=F&background=1877f2&color=fff' },
                { platform_id: 4, api_name: 'Twitter', account_name: '@pablodev', profile_photo_url: 'https://ui-avatars.com/api/?name=X&background=000&color=fff' }
            ];
            renderPlatformSelector();
            selectPlatform(state.platforms[0]);
        }
    }

    function renderPlatformSelector() {
        elements.platformSelector.innerHTML = '';
        state.platforms.forEach(p => {
            const apiName = p.api_name.toLowerCase();
            const iconData = PLATFORM_ICONS[apiName] || { color: 'text-gray-500', path: '' };
            
            const btn = document.createElement('button');
            const isActive = state.currentPlatform && state.currentPlatform.platform_id === p.platform_id;
            
            btn.className = `flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                isActive 
                ? 'bg-gray-800 text-white border-gray-800 shadow-sm' 
                : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
            }`;
            const svg = `<svg class="w-3.5 h-3.5 ${isActive ? 'text-white' : iconData.color}" fill="currentColor" viewBox="0 0 24 24"><path d="${iconData.path}"/></svg>`;
            
            btn.innerHTML = `${svg} <span>${p.account_name}</span>`;
            btn.onclick = () => selectPlatform(p);
            elements.platformSelector.appendChild(btn);
        });
    }

    function selectPlatform(platform) {
        state.currentPlatform = platform;
        elements.platformId.value = platform.platform_id;
        const apiName = platform.api_name.toLowerCase();
        
        // Update Post Type Selector
        elements.postTypeSelector.innerHTML = '';
        let types = ['Post'];
        if (apiName === 'instagram') types = ['Post', 'Reel', 'Story'];
        
        types.forEach(t => {
            const label = document.createElement('label');
            label.className = 'flex items-center gap-2 cursor-pointer group';
            label.innerHTML = `
                <input type="radio" name="postType" value="${t}" ${t === state.currentPostType ? 'checked' : ''} class="w-4 h-4 text-gray-800 border-gray-300 focus:ring-gray-800">
                <span class="group-hover:text-gray-800 transition">${t}</span>
            `;
            label.querySelector('input').onchange = (e) => {
                state.currentPostType = e.target.value;
                updatePreview();
            };
            elements.postTypeSelector.appendChild(label);
        });

        // Update active icon
        const iconData = PLATFORM_ICONS[apiName];
        if(iconData) {
            elements.activePlatformIcon.innerHTML = `<svg class="w-3 h-3 ${iconData.color}" fill="currentColor" viewBox="0 0 24 24"><path d="${iconData.path}"/></svg>`;
        }

        renderPlatformSelector();
        updatePreview();
    }

    // --- Media Rendering Logic ---
    function renderMediaForPreview(items, layoutType = 'feed') {
        if (!items || items.length === 0) {
            return `<div class="w-full h-full bg-gray-100 flex flex-col items-center justify-center text-gray-400 border border-gray-100 min-h-[300px]"><svg class="w-8 h-8 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg><span class="text-xs">No media</span></div>`;
        }

        // 1. Single Video
        if (items[0].type === 'video') {
            const css = layoutType === 'vertical' ? 'absolute inset-0 w-full h-full object-cover z-0' : 'w-full h-auto object-cover block';
            return `<video src="${items[0].src}" class="${css}" controls autoplay muted loop playsinline></video>`;
        }

        // 2. Images
        if (items.length === 1) {
            const css = layoutType === 'vertical' ? 'absolute inset-0 w-full h-full object-cover z-0' : 'w-full h-auto object-cover block';
            return `<img src="${items[0].src}" class="${css}">`;
        } else {
            // Multiple Images (Carousel)
            // Note: Vertical layout for carousel usually just shows first image dimmed or simple slideshow. 
            // For Feed, we make a scrollable area.
            if (layoutType === 'vertical') {
                return `<img src="${items[0].src}" class="absolute inset-0 w-full h-full object-cover z-0">`; // Story/Reel usually doesn't do carousel easily in preview
            }
            
            // Generate Horizontal Scroll Carousel
            let slides = items.map(item => `
                <div class="w-full flex-shrink-0 snap-center relative">
                    <img src="${item.src}" class="w-full h-auto object-cover aspect-square">
                </div>
            `).join('');
            
            return `
                <div class="relative group">
                    <div class="flex overflow-x-auto snap-x snap-mandatory scrollbar-hide w-full">
                        ${slides}
                    </div>
                    <div class="absolute top-2 right-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded-full font-medium">
                        1/${items.length}
                    </div>
                </div>
            `;
        }
    }

    function getPreviewHtml(platformName, p, caption, mediaItems, postType) {
        const name = p.account_name;
        const avatar = p.profile_photo_url || 'https://www.gravatar.com/avatar/0?d=mp';
        document.getElementById("UserDpLg").innerHTML=`<img src="${avatar}" class="w-full h-full rounded-full border-2 border-white object-cover" alt="User">`;

        // Generate Media HTML based on context
        const feedMedia = renderMediaForPreview(mediaItems, 'feed');
        const verticalMedia = renderMediaForPreview(mediaItems, 'vertical');

        if (platformName === 'instagram') {
            // 1. STORY
            if (postType === 'Story') {
                return `
                <div class="relative w-[300px] h-[530px] bg-black rounded-xl overflow-hidden shadow-lg mx-auto border border-gray-300 font-sans text-white">
                    ${verticalMedia}
                    <div class="absolute top-0 left-0 right-0 p-3 z-10 bg-gradient-to-b from-black/60 to-transparent">
                        <div class="flex gap-1 h-1 mb-3">
                            <div class="flex-1 bg-white/40 rounded-full overflow-hidden"><div class="h-full bg-white w-3/4"></div></div>
                            <div class="flex-1 bg-white/40 rounded-full"></div>
                        </div>
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <img src="${avatar}" class="w-8 h-8 rounded-full border border-gray-300">
                                <span class="text-sm font-semibold text-white shadow-black drop-shadow-md">${name}</span>
                                <span class="text-xs text-gray-300">12h</span>
                            </div>
                            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                        </div>
                    </div>
                    <div class="absolute bottom-0 left-0 right-0 p-4 pb-6 flex items-center gap-3 z-10 bg-gradient-to-t from-black/60 to-transparent">
                        <div class="flex-1 h-10 border border-white/30 rounded-full px-4 flex items-center text-white/70 text-sm">Send message</div>
                        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path></svg>
                        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                    </div>
                    <div class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center z-10 w-3/4 pointer-events-none">
                        <p class="text-white text-lg font-bold drop-shadow-md break-words">${caption}</p>
                    </div>
                </div>`;
            }

            // 2. REEL
            if (postType === 'Reel') {
                return `
                <div class="relative w-[300px] h-[530px] bg-black rounded-xl overflow-hidden shadow-lg mx-auto border border-gray-300 font-sans text-white">
                    ${verticalMedia}
                    <div class="absolute top-4 right-4 z-10">
                        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path></svg>
                    </div>

                    <div class="absolute bottom-4 right-2 z-20 flex flex-col items-center gap-4">
                        <div class="flex flex-col items-center gap-1">
                             <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path></svg>
                             <span class="text-xs font-semibold">Likes</span>
                        </div>
                        <div class="flex flex-col items-center gap-1">
                             <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
                             <span class="text-xs font-semibold">123</span>
                        </div>
                        <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z"></path></svg>
                    </div>

                    <div class="absolute bottom-0 left-0 right-12 p-4 pb-6 z-10 bg-gradient-to-t from-black/80 to-transparent">
                        <div class="flex items-center gap-2 mb-2">
                            <img src="${avatar}" class="w-8 h-8 rounded-full border border-white">
                            <span class="font-semibold text-sm shadow-black drop-shadow-md">${name}</span>
                            <span class="px-2 py-0.5 border border-white/50 rounded text-[10px] font-medium">Follow</span>
                        </div>
                        <div class="text-sm text-white line-clamp-2 mb-2">${caption || 'Reel caption goes here... #fyp'}</div>
                        <div class="flex items-center gap-2 text-xs opacity-90">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>
                            <span class="marquee">Original Audio - ${name}</span>
                        </div>
                    </div>
                </div>`;
            }

            // 3. INSTAGRAM FEED POST (Default)
            return `
    <div class="bg-white border border-gray-200 rounded-xl w-full font-sans text-[14px] shadow-sm max-w-[470px] mx-auto overflow-hidden">
        <div class="flex items-center justify-between px-3 py-3">
            <div class="flex items-center gap-2">
                <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-yellow-400 to-pink-600 p-[1px]">
                    <img src="${avatar}" class="w-full h-full rounded-full border border-white object-cover shadow-sm">
                </div>
                <div class="flex items-center gap-1">
                    <span class="font-bold text-gray-900">${name}</span>
                    <span class="text-gray-500 mx-0.5">•</span>
                    <span class="text-gray-500">1d</span>
                    <span class="text-gray-500 mx-0.5">•</span>
                    <button class="text-indigo-600 font-bold text-[13px] hover:text-black transition">Follow</button>
                </div>
            </div>
            <button class="text-gray-600 hover:text-gray-400">
                <svg aria-label="More options" fill="currentColor" height="24" viewBox="0 0 24 24" width="24"><circle cx="12" cy="12" r="1.5"></circle><circle cx="6" cy="12" r="1.5"></circle><circle cx="18" cy="12" r="1.5"></circle></svg>
            </button>
        </div>

        <div class="w-full bg-black flex items-center justify-center min-h-[300px] border-y border-gray-50">
            ${feedMedia}
        </div>

        <div class="p-3">
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-4">
                    <div class="flex items-center gap-1.5 cursor-pointer group">
                        <svg aria-label="Like" class="group-hover:text-gray-500 transition" fill="currentColor" height="24" viewBox="0 0 24 24" width="24"><path d="M16.792 3.904A4.989 4.989 0 0 1 21.5 9.122c0 3.072-2.652 4.959-5.197 7.222-2.512 2.243-3.865 3.469-4.303 3.752-.477-.309-2.143-1.823-4.303-3.752C5.141 14.072 2.5 12.167 2.5 9.122a4.989 4.989 0 0 1 4.708-5.218 4.21 4.21 0 0 1 3.675 1.941c.84 1.175.98 1.763 1.12 1.763s.278-.588 1.11-1.766a4.17 4.17 0 0 1 3.679-1.938m0-2a6.04 6.04 0 0 0-4.797 2.127 6.052 6.052 0 0 0-4.787-2.127A6.985 6.985 0 0 0 .5 9.122c0 3.61 2.55 5.827 5.015 7.97.283.246.569.494.853.747l1.027.918a44.998 44.998 0 0 0 3.518 3.018 2 2 0 0 0 2.174 0 45.263 45.263 0 0 0 3.626-3.115l.922-.824c.293-.26.59-.519.885-.774 2.334-2.025 4.98-4.32 4.98-7.94a6.985 6.985 0 0 0-6.708-7.218Z"></path></svg>
                        <span class="text-sm font-semibold">124K</span>
                    </div>
                    <div class="flex items-center gap-1.5 cursor-pointer group">
                        <svg aria-label="Comment" class="group-hover:text-gray-500 transition" fill="currentColor" height="24" viewBox="0 0 24 24" width="24"><path d="M20.656 17.008a9.993 9.993 0 1 0-3.59 3.615L22 22Z" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="2"></path></svg>
                        <span class="text-sm font-semibold">2.6K</span>
                    </div>
                    <div class="flex items-center gap-1.5 cursor-pointer group">
                        <svg aria-label="Repost" class="group-hover:text-gray-500 transition" fill="currentColor" height="24" viewBox="0 0 24 24" width="24"><path d="M19.998 9.497a1 1 0 0 0-1 1v4.228a3.274 3.274 0 0 1-3.27 3.27h-5.313l1.791-1.787a1 1 0 0 0-1.412-1.416L7.29 18.287a1.004 1.004 0 0 0-.294.707v.001c0 .023.012.042.013.065a.923.923 0 0 0 .281.643l3.502 3.504a1 1 0 0 0 1.414-1.414l-1.797-1.798h5.318a5.276 5.276 0 0 0 5.27-5.27v-4.228a1 1 0 0 0-1-1Zm-6.41-3.496-1.795 1.795a1 1 0 1 0 1.414 1.414l3.5-3.5a1.003 1.003 0 0 0 0-1.417l-3.5-3.5a1 1 0 0 0-1.414 1.414l1.794 1.794H8.27A5.277 5.277 0 0 0 3 9.271V13.5a1 1 0 0 0 2 0V9.271a3.275 3.275 0 0 1 3.271-3.27Z"></path></svg>
                        <span class="text-sm font-semibold">663</span>
                    </div>
                    <div class="cursor-pointer group">
                        <svg aria-label="Share" class="group-hover:text-gray-500 transition" fill="currentColor" height="24" viewBox="0 0 24 24" width="24"><path d="M13.973 20.046 21.77 6.928C22.8 5.195 21.55 3 19.535 3H4.466C2.138 3 .984 5.825 2.646 7.456l4.842 4.752 1.723 7.121c.548 2.266 3.571 2.721 4.762.717Z" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="2"></path><line fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" x1="7.488" x2="15.515" y1="12.208" y2="7.641"></line></svg>
                    </div>
                </div>
                <div class="cursor-pointer group">
                    <svg aria-label="Save" class="group-hover:text-gray-500 transition" fill="currentColor" height="24" viewBox="0 0 24 24" width="24"><polygon fill="none" points="20 21 12 13.44 4 21 4 3 20 3 20 21" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></polygon></svg>
                </div>
            </div>
            
            <div class="text-[14px] text-gray-900 leading-snug">
                <span class="font-bold mr-1">${name}</span>${caption || 'Write a caption...'}
            </div>
            <div class="text-gray-500 text-[13px] mt-2 cursor-pointer hover:opacity-70">View all 12 comments</div>
        </div>
    </div>`;
        }

        if (platformName === 'facebook') {
            return `
            <div class="bg-white border border-gray-200 rounded-lg w-full font-sans shadow-sm max-w-[500px] mx-auto overflow-hidden">
                <div class="p-3 flex items-start justify-between">
                    <div class="flex gap-2">
                        <div class="relative">
                            <img src="${avatar}" class="w-10 h-10 rounded-full border border-gray-100 object-cover">
                            <div class="absolute inset-0 rounded-full border border-black/5"></div>
                        </div>
                        <div>
                            <div class="flex items-center gap-1">
                                <span class="font-bold text-[15px] text-gray-900 leading-tight hover:underline cursor-pointer">${name}</span>
                                <svg viewBox="0 0 12 13" width="12" height="12" fill="currentColor" class="text-[#0866FF] mb-0.5"><title>Verified account</title><g fill-rule="evenodd" transform="translate(-98 -917)"><path d="m106.853 922.354-3.5 3.5a.499.499 0 0 1-.706 0l-1.5-1.5a.5.5 0 1 1 .706-.708l1.147 1.147 3.147-3.147a.5.5 0 1 1 .706.708m3.078 2.295-.589-1.149.588-1.15a.633.633 0 0 0-.219-.82l-1.085-.7-.065-1.287a.627.627 0 0 0-.6-.603l-1.29-.066-.703-1.087a.636.636 0 0 0-.82-.217l-1.148.588-1.15-.588a.631.631 0 0 0-.82.22l-.701 1.085-1.289.065a.626.626 0 0 0-.6.6l-.066 1.29-1.088.702a.634.634 0 0 0-.216.82l.588 1.149-.588 1.15a.632.632 0 0 0 .219.819l1.085.701.065 1.286c.014.33.274.59.6.604l1.29.065.703 1.088c.177.27.53.362.82.216l1.148-.588 1.15.589a.629.629 0 0 0 .82-.22l.701-1.085 1.286-.064a.627.627 0 0 0 .604-.601l.065-1.29 1.088-.703a.633.633 0 0 0 .216-.819"></path></g></svg>
                            </div>
                            <div class="flex items-center gap-1 text-[13px] text-gray-500 font-normal">
                                <span>Just now</span>
                                <span>·</span>
                                <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor" title="Shared with Public"><title>Shared with Public</title><g fill-rule="evenodd" transform="translate(-448 -544)"><g><path d="M109.5 408.5c0 3.23-2.04 5.983-4.903 7.036l.07-.036c1.167-1 1.814-2.967 2-3.834.214-1 .303-1.3-.5-1.96-.31-.253-.677-.196-1.04-.476-.246-.19-.356-.59-.606-.73-.594-.337-1.107.11-1.954.223a2.666 2.666 0 0 1-1.15-.123c-.007 0-.007 0-.013-.004l-.083-.03c-.164-.082-.077-.206.006-.36h-.006c.086-.17.086-.376-.05-.529-.19-.214-.54-.214-.804-.224-.106-.003-.21 0-.313.004l-.003-.004c-.04 0-.084.004-.124.004h-.037c-.323.007-.666-.034-.893-.314-.263-.353-.29-.733.097-1.09.28-.26.863-.8 1.807-.22.603.37 1.166.667 1.666.5.33-.11.48-.303.094-.87a1.128 1.128 0 0 1-.214-.73c.067-.776.687-.84 1.164-1.2.466-.356.68-.943.546-1.457-.106-.413-.51-.873-1.28-1.01a7.49 7.49 0 0 1 6.524 7.434" transform="translate(354 143.5)"></path><path d="M104.107 415.696A7.498 7.498 0 0 1 94.5 408.5a7.48 7.48 0 0 1 3.407-6.283 5.474 5.474 0 0 0-1.653 2.334c-.753 2.217-.217 4.075 2.29 4.075.833 0 1.4.561 1.333 2.375-.013.403.52 1.78 2.45 1.89.7.04 1.184 1.053 1.33 1.74.06.29.127.65.257.97a.174.174 0 0 0 .193.096" transform="translate(354 143.5)"></path><path fill-rule="nonzero" d="M110 408.5a8 8 0 1 1-16 0 8 8 0 0 1 16 0zm-1 0a7 7 0 1 0-14 0 7 7 0 0 0 14 0z" transform="translate(354 143.5)"></path></g></g></svg>
                            </div>
                        </div>
                    </div>
                    <div class="flex gap-2">
                        <button class="p-2 hover:bg-gray-100 rounded-full transition text-gray-500">
                            <svg viewBox="0 0 20 20" width="20" height="20" fill="currentColor"><g fill-rule="evenodd" transform="translate(-446 -350)"><path d="M458 360a2 2 0 1 1-4 0 2 2 0 0 1 4 0m6 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0m-12 0a2 2 0 1 1-4 0 2 2 0 0 1 4 0"></path></g></svg>
                        </button>
                        <button class="p-2 hover:bg-gray-100 rounded-full transition text-gray-500">
                            <svg viewBox="0 0 20 20" width="20" height="20" fill="currentColor"><path d="M15.543 3.043a1 1 0 1 1 1.414 1.414L11.414 10l5.543 5.542a1 1 0 0 1-1.414 1.415L10 11.414l-5.543 5.543a1 1 0 0 1-1.414-1.415L8.586 10 3.043 4.457a1 1 0 1 1 1.414-1.414L10 8.586l5.543-5.543z"></path></svg>
                        </button>
                    </div>
                </div>

                <div class="px-4 pb-3 text-sm text-gray-900">
                    ${caption || 'What\'s on your mind?'}
                </div>

                <div class="w-full bg-gray-50 border-y border-gray-100 min-h-[300px] flex items-center justify-center">
                    ${feedMedia}
                </div>

                <div class="px-4 py-2 flex items-center justify-between text-[14px] text-gray-500">
                    <div class="flex items-center gap-1.5 cursor-pointer hover:underline">
                        <div class="w-[18px] h-[18px] rounded-full bg-blue-600 flex items-center justify-center">
                             <svg viewBox="0 0 16 16" width="10" height="10" fill="white"><path d="M7.3014 3.8662a.6974.6974 0 0 1 .6974-.6977c.6742 0 1.2207.5465 1.2207 1.2206v1.7464a.101.101 0 0 0 .101.101h1.7953c.992 0 1.7232.9273 1.4917 1.892l-.4572 1.9047a2.301 2.301 0 0 1-2.2374 1.764H6.9185a.5752.5752 0 0 1-.5752-.5752V7.7384c0-.4168.097-.8278.2834-1.2005l.2856-.5712a3.6878 3.6878 0 0 0 .3893-1.6509l-.0002-.4496ZM4.367 7a.767.767 0 0 0-.7669.767v3.2598a.767.767 0 0 0 .767.767h.767a.3835.3835 0 0 0 .3835-.3835V7.3835A.3835.3835 0 0 0 5.134 7h-.767Z"></path></svg>
                        </div>
                        <span class="hover:text-gray-900">32K</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <span class="hover:underline cursor-pointer">432 comments</span>
                        <span class="hover:underline cursor-pointer">177 shares</span>
                    </div>
                </div>

                <div class="mx-3 py-1 flex justify-between border-t border-gray-200 text-gray-500 font-semibold text-[14px]">
                    <button class="flex-1 flex items-center justify-center gap-2 py-2 hover:bg-gray-100 rounded-md transition group">
                        <i style="background-image: url('https://static.xx.fbcdn.net/rsrc.php/v4/yp/r/SUp2gyEkEE4.png'); background-position: 0px -854px; width: 20px; height: 20px;" class="filter brightness-90 contrast-75"></i>
                        <span>Like</span>
                    </button>
                    <button class="flex-1 flex items-center justify-center gap-2 py-2 hover:bg-gray-100 rounded-md transition">
                        <i style="background-image: url('https://static.xx.fbcdn.net/rsrc.php/v4/yp/r/SUp2gyEkEE4.png'); background-position: 0px -812px; width: 20px; height: 20px;" class="filter brightness-90 contrast-75"></i>
                        <span>Comment</span>
                    </button>
                    <button class="flex-1 flex items-center justify-center gap-2 py-2 hover:bg-gray-100 rounded-md transition">
                        <i style="background-image: url('https://static.xx.fbcdn.net/rsrc.php/v4/yp/r/SUp2gyEkEE4.png'); background-position: 0px -896px; width: 20px; height: 20px;" class="filter brightness-90 contrast-75"></i>
                        <span>Share</span>
                    </button>
                </div>
            </div>`;
        }

        // --- TWITTER / X ---
        if (platformName === 'x' || platformName === 'twitter') {
            return `
            <div class="bg-white border border-gray-100 rounded-lg w-full font-sans p-3 shadow-sm">
                <div class="flex gap-3">
                    <img src="${avatar}" class="w-10 h-10 rounded-full">
                    <div class="flex-1">
                        <div class="flex items-center gap-1 text-sm">
                            <span class="font-bold text-gray-900">${name}</span>
                            <span class="text-gray-500">@handle · 1m</span>
                        </div>
                        <div class="text-sm text-gray-900 mt-0.5 mb-2 whitespace-pre-wrap">${caption || 'What is happening?!'}</div>
                        ${mediaItems.length ? `<div class="rounded-xl overflow-hidden border border-gray-200 mb-2">${feedMedia}</div>` : ''}
                        <div class="flex justify-between text-gray-400 max-w-xs mt-2">
                             <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
                             <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                             <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path></svg>
                        </div>
                    </div>
                </div>
            </div>`;
        }
        
if (platformName === 'linkedin') {
    return `
    <div class="bg-white border border-gray-200 rounded-lg w-full font-sans shadow-md overflow-hidden max-w-[550px] mx-auto">
        <div class="px-3 pt-3 flex justify-between items-center">
            <span class="text-[12px] text-gray-500 font-normal"></span>
            <div class="flex gap-2">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" class="text-gray-600"><path d="M3.25 8C3.25 8.69 2.69 9.25 2 9.25C1.31 9.25 0.75 8.69 0.75 8C0.75 7.31 1.31 6.75 2 6.75C2.69 6.75 3.25 7.31 3.25 8ZM14 6.75C13.31 6.75 12.75 7.31 12.75 8C12.75 8.69 13.31 9.25 14 9.25C14.69 9.25 15.25 8.69 15.25 8C15.25 7.31 14.69 6.75 14 6.75ZM8 6.75C7.31 6.75 6.75 7.31 6.75 8C6.75 8.69 7.31 9.25 8 9.25C8.69 9.25 9.25 8.69 9.25 8C9.25 7.31 8.69 6.75 8 6.75Z" fill="currentColor"></path></svg>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" class="text-gray-600"><path d="M13.78 12.72C14.07 13.01 14.07 13.49 13.78 13.78C13.63 13.93 13.44 14 13.25 14C13.06 14 12.87 13.93 12.72 13.78L8 9.06L3.28 13.78C3.13 13.93 2.94 14 2.75 14C2.56 14 2.37 13.93 2.22 13.78C1.93 13.49 1.93 13.01 2.22 12.72L6.94 8L2.22 3.28C1.93 2.99 1.93 2.51 2.22 2.22C2.51 1.93 2.99 1.93 3.28 2.22L8 6.94L12.72 2.22C13.01 1.93 13.49 1.93 13.78 2.22C14.07 2.51 14.07 2.99 13.78 3.28L9.06 8L13.78 12.72Z" fill="currentColor"></path></svg>
            </div>
        </div>
        
        <hr class="mt-2 border-gray-100">

        <div class="p-3 flex items-start justify-between">
            <div class="flex gap-2">
                <img src="${avatar}" class="w-12 h-12 rounded-full object-cover">
                <div class="flex flex-col">
                    <div class="flex items-center gap-1">
                        <span class="font-bold text-sm text-gray-900 hover:underline cursor-pointer">${name}</span>
                        <span class="text-gray-500 text-[12px] flex items-center gap-1">
                            • 3rd+
                        </span>
                    </div>
                    <span class="text-[12px] text-gray-500 leading-tight">Professional Developer</span>
                    <div class="flex items-center gap-1 text-[12px] text-gray-500">
                        <span>1d •</span>
                        <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor"><path d="M8 1a7 7 0 107 7 7 7 0 00-7-7zM3 8a5 5 0 011-3l.55.55A1.5 1.5 0 015 6.62v1.07a.75.75 0 00.22.53l.56.56a.75.75 0 00.53.22H7v.69a.75.75 0 00.22.53l.56.56a.75.75 0 01.22.53V13a5 5 0 01-5-5zm6.24 4.83l2-2.46a.75.75 0 00.09-.8l-.58-1.16A.76.76 0 0010 8H7v-.19a.51.51 0 01.28-.45l.38-.19a.74.74 0 01.68 0L9 7.5l.38-.7a1 1 0 00.12-.48v-.85a.78.78 0 01.21-.53l1.07-1.09a5 5 0 01-1.54 9z"></path></svg>
                    </div>
                </div>
            </div>
            <button class="flex items-center gap-1 text-[#0a66c2] font-bold text-sm hover:bg-blue-50 px-2 py-1 rounded">
                <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M14 9H9v5H7V9H2V7h5V2h2v5h5z"></path></svg>
                Follow
            </button>
        </div>

        <div class="px-3 pb-2 text-[14px] text-gray-800 leading-normal whitespace-pre-wrap">${caption || 'Your Caption Here....'}</div>
        
        <div class="w-full border-t border-gray-100 bg-gray-50">
            ${feedMedia}
        </div>

        <div class="px-3 py-2 flex justify-between items-center border-b border-gray-100">
            <div class="flex items-center -space-x-1">
                <div class="w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center border border-white"><svg viewBox="0 0 16 16" width="10" height="10" fill="white"><path d="M8.82 2.2a1.32 1.32 0 10-1.64 0 1.32 1.32 0 001.64 0zM5.5 13H4a1 1 0 01-1-1V7a1 1 0 011-1h1.5a1 1 0 011 1v5a1 1 0 01-1 1zM13.5 10a1 1 0 01-1 1H8v1h3a2 2 0 012 2v.5a.5.5 0 01-.5.5H5.83l-1.32-3H3V7h1.51l1.32-3h4a2 2 0 012 2v1H11a1 1 0 011 1v1h.5a1 1 0 011 1z"></path></svg></div>
                <div class="w-4 h-4 rounded-full bg-red-500 flex items-center justify-center border border-white"><svg viewBox="0 0 16 16" width="10" height="10" fill="white"><path d="M8 14s-6-3.68-6-7.5C2 4.14 4.14 2 6.5 2 7.7 2 8.5 2.5 9 3c.5-.5 1.3-1 2.5-1 2.36 0 4.5 2.14 4.5 4.5 0 3.82-6 7.5-6 7.5z"></path></svg></div>
                <span class="pl-4 text-[12px] text-gray-500 hover:text-blue-600 cursor-pointer">89</span>
            </div>
            <div class="flex gap-2 text-[12px] text-gray-500">
                <span class="hover:text-blue-600 cursor-pointer hover:underline">1 comment</span>
                <span>•</span>
                <span class="hover:text-blue-600 cursor-pointer hover:underline">4 reposts</span>
            </div>
        </div>

        <div class="flex px-1 py-1">
            <button class="flex-1 flex items-center justify-center gap-2 py-3 hover:bg-gray-100 rounded transition text-gray-600 font-semibold text-xs">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-thumbs-up-icon lucide-thumbs-up"><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/><path d="M7 10v12"/></svg>
                Like
            </button>
            <button class="flex-1 flex items-center justify-center gap-2 py-3 hover:bg-gray-100 rounded transition text-gray-600 font-semibold text-xs">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-message-square-icon lucide-message-square"><path d="M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z"/></svg>
                Comment
            </button>
            <button class="flex-1 flex items-center justify-center gap-2 py-3 hover:bg-gray-100 rounded transition text-gray-600 font-semibold text-xs">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-repeat2-icon lucide-repeat-2"><path d="m2 9 3-3 3 3"/><path d="M13 18H7a2 2 0 0 1-2-2V6"/><path d="m22 15-3 3-3-3"/><path d="M11 6h6a2 2 0 0 1 2 2v10"/></svg>
                Repost
            </button>
            <button class="flex-1 flex items-center justify-center gap-2 py-3 hover:bg-gray-100 rounded transition text-gray-600 font-semibold text-xs">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-send-icon lucide-send"><path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/></svg>
                Send
            </button>
        </div>
    </div>`;
}

        // --- THREADS (Updated with authentic meta-scraped SVGs) ---
        if (platformName === 'threads') {
            return `
            <div class="bg-white w-full font-sans p-4 border border-gray-200 shadow-sm rounded-xl max-w-[420px] mx-auto">
                <div class="flex gap-3">
                    <div class="flex flex-col items-center shrink-0">
                        <img src="${avatar}" class="w-9 h-9 rounded-full border border-gray-100 object-cover">
                        <div class="w-0.5 flex-1 bg-gray-100 mt-2 rounded-full mb-2"></div> 
                    </div>
                    
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between mb-1">
                            <div class="flex items-center gap-2">
                                <span class="font-bold text-sm text-black leading-none">${name}</span>
                                <span class="text-gray-400 text-sm leading-none font-normal">23h</span>
                            </div>
                            <svg aria-label="More" role="img" viewBox="0 0 24 24" class="w-5 h-5 text-gray-400"><circle cx="12" cy="12" r="1.5"/><circle cx="6" cy="12" r="1.5"/><circle cx="18" cy="12" r="1.5"/></svg>
                        </div>
                        
                        <div class="text-[15px] text-gray-900 leading-snug whitespace-pre-wrap mb-2">${caption || 'Start a thread...'}</div>
                        
                        ${mediaItems.length > 0 ? `<div class="mt-2 rounded-xl overflow-hidden border border-gray-100 shadow-sm mb-3">${feedMedia}</div>` : ''}
                        
                        <div class="flex items-center gap-1 -ml-2">
                            <div class="p-2 flex items-center gap-1.5 cursor-pointer hover:bg-gray-50 rounded-full transition">
                                <svg aria-label="Like" role="img" viewBox="0 0 18 18" class="w-[18px] h-[18px]"><path d="M1.34375 7.53125L1.34375 7.54043C1.34374 8.04211 1.34372 8.76295 1.6611 9.65585C1.9795 10.5516 2.60026 11.5779 3.77681 12.7544C5.59273 14.5704 7.58105 16.0215 8.33387 16.5497C8.73525 16.8313 9.26573 16.8313 9.66705 16.5496C10.4197 16.0213 12.4074 14.5703 14.2232 12.7544C15.3997 11.5779 16.0205 10.5516 16.3389 9.65585C16.6563 8.76296 16.6563 8.04211 16.6562 7.54043V7.53125C16.6562 5.23466 15.0849 3.25 12.6562 3.25C11.5214 3.25 10.6433 3.78244 9.99228 4.45476C9.59009 4.87012 9.26356 5.3491 9 5.81533C8.73645 5.3491 8.40991 4.87012 8.00772 4.45476C7.35672 3.78244 6.47861 3.25 5.34375 3.25C2.9151 3.25 1.34375 5.23466 1.34375 7.53125Z" stroke="currentColor" fill="none" stroke-width="1.25"></path></svg>
                                <span class="text-xs text-gray-500 font-normal">136</span>
                            </div>
                            <div class="p-2 flex items-center gap-1.5 cursor-pointer hover:bg-gray-50 rounded-full transition">
                                <svg aria-label="Reply" role="img" viewBox="0 0 18 18" class="w-[18px] h-[18px]"><path d="M15.376 13.2177L16.2861 16.7955L12.7106 15.8848C12.6781 15.8848 12.6131 15.8848 12.5806 15.8848C11.3779 16.5678 9.94767 16.8931 8.41995 16.7955C4.94194 16.5353 2.08152 13.7381 1.72397 10.2578C1.2689 5.63919 5.13697 1.76863 9.75264 2.22399C13.2307 2.58177 16.0261 5.41151 16.2861 8.92429C16.4161 10.453 16.0586 11.8841 15.376 13.0876C15.376 13.1526 15.376 13.1852 15.376 13.2177Z" stroke="currentColor" fill="none" stroke-linejoin="round" stroke-width="1.25"></path></svg>
                                <span class="text-xs text-gray-500 font-normal">13</span>
                            </div>
                            <div class="p-2 flex items-center gap-1.5 cursor-pointer hover:bg-gray-50 rounded-full transition">
                                <svg aria-label="Repost" role="img" viewBox="0 0 18 18" class="w-[18px] h-[18px] text-gray-900"><path d="M6.41256 1.23531C6.6349 0.971277 7.02918 0.937481 7.29321 1.15982L9.96509 3.40982C10.1022 3.52528 10.1831 3.69404 10.1873 3.87324C10.1915 4.05243 10.1186 4.2248 9.98706 4.34656L7.31518 6.81971C7.06186 7.05419 6.66643 7.03892 6.43196 6.7856C6.19748 6.53228 6.21275 6.13685 6.46607 5.90237L7.9672 4.51289H5.20312C3.68434 4.51289 2.45312 5.74411 2.45312 7.26289V9.51289V11.7629C2.45312 13.2817 3.68434 14.5129 5.20312 14.5129C5.5483 14.5129 5.82812 14.7927 5.82812 15.1379C5.82812 15.4831 5.5483 15.7629 5.20312 15.7629C2.99399 15.7629 1.20312 13.972 1.20312 11.7629V9.51289V7.26289C1.20312 5.05375 2.99399 3.26289 5.20312 3.26289H7.85002L6.48804 2.11596C6.22401 1.89362 6.19021 1.49934 6.41256 1.23531Z" fill="currentColor"></path><path d="M11.5874 17.7904C11.3651 18.0545 10.9708 18.0883 10.7068 17.8659L8.03491 15.6159C7.89781 15.5005 7.81687 15.3317 7.81267 15.1525C7.80847 14.9733 7.8814 14.801 8.01294 14.6792L10.6848 12.206C10.9381 11.9716 11.3336 11.9868 11.568 12.2402C11.8025 12.4935 11.7872 12.8889 11.5339 13.1234L10.0328 14.5129H12.7969C14.3157 14.5129 15.5469 13.2816 15.5469 11.7629V9.51286V7.26286C15.5469 5.74408 14.3157 4.51286 12.7969 4.51286C12.4517 4.51286 12.1719 4.23304 12.1719 3.88786C12.1719 3.54269 12.4517 3.26286 12.7969 3.26286C15.006 3.26286 16.7969 5.05373 16.7969 7.26286V9.51286V11.7629C16.7969 13.972 15.006 15.7629 12.7969 15.7629H10.15L11.512 16.9098C11.776 17.1321 11.8098 17.5264 11.5874 17.7904Z" fill="currentColor"></path></svg>
                                <span class="text-xs text-gray-500 font-normal">11</span>
                            </div>
                            <div class="p-2 flex items-center gap-1.5 cursor-pointer hover:bg-gray-50 rounded-full transition">
                                <svg aria-label="Share" role="img" viewBox="0 0 18 18" class="w-[18px] h-[18px]"><path d="M15.6097 4.09082L6.65039 9.11104" stroke="currentColor" fill="none" stroke-linejoin="round" stroke-width="1.25"></path><path d="M7.79128 14.439C8.00463 15.3275 8.11131 15.7718 8.33426 15.932C8.52764 16.071 8.77617 16.1081 9.00173 16.0318C9.26179 15.9438 9.49373 15.5501 9.95761 14.7628L15.5444 5.2809C15.8883 4.69727 16.0603 4.40546 16.0365 4.16566C16.0159 3.95653 15.9071 3.76612 15.7374 3.64215C15.5428 3.5 15.2041 3.5 14.5267 3.5H3.71404C2.81451 3.5 2.36474 3.5 2.15744 3.67754C1.97758 3.83158 1.88253 4.06254 1.90186 4.29856C1.92415 4.57059 2.24363 4.88716 2.88259 5.52032L6.11593 8.7243C6.26394 8.87097 6.33795 8.94431 6.39784 9.02755C6.451 9.10144 6.4958 9.18101 6.53142 9.26479C6.57153 9.35916 6.59586 9.46047 6.64451 9.66309L7.79128 14.439Z" stroke="currentColor" fill="none" stroke-linejoin="round" stroke-width="1.25"></path></svg>
                                <span class="text-xs text-gray-500 font-normal">238</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
        }

        return `<div class="p-4 border border-dashed text-gray-400 text-center">Preview not available</div>`;
    }

    function updatePreview() {
        if (!state.currentPlatform) {
            elements.preview.innerHTML = '<div class="text-center text-gray-400 mt-10">Select a platform to preview</div>';
            return;
        }

        const apiName = state.currentPlatform.api_name.toLowerCase();
        
        elements.previewTitle.innerHTML = ` ${state.currentPlatform.api_name.charAt(0).toUpperCase() + state.currentPlatform.api_name.slice(1)} Preview
            <svg title="Platform preview of ${state.currentPlatform.api_name}" class="w-4 h-4 text-gray-400 ml-auto cursor-pointer" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        `;

        elements.preview.innerHTML = getPreviewHtml(
            apiName, 
            state.currentPlatform, 
            elements.caption.value, 
            state.mediaItems,
            state.currentPostType
        );
    }

    // --- Helper: Read File as Data URL ---
    function readFileAsDataURL(file) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.readAsDataURL(file);
        });
    }

    // --- Event Listeners ---
    
    // File Input Handling (Updated for Multiple & Video)
    elements.fileInput.addEventListener('change', async (e) => {
        const files = Array.from(e.target.files);
        if (files.length === 0) return;

        // Reset state
        state.mediaItems = [];
        state.rawFiles = [];

        // Determine if there's a video (Single Video Support only)
        const videoFile = files.find(f => f.type.startsWith('video/'));

        if (videoFile) {
            // Case: Video (Only allow 1)
            state.rawFiles = [videoFile];
            const src = await readFileAsDataURL(videoFile);
            state.mediaItems.push({ type: 'video', src: src });
            
            // UI Update for Video
            elements.inputMediaImg.classList.add('hidden');
            elements.inputMediaVideo.src = src;
            elements.inputMediaVideo.classList.remove('hidden');
            elements.mediaCountOverlay.classList.add('hidden');
        } else {
            // Case: Images (Allow Multiple)
            state.rawFiles = files; // Store all
            
            // Process all images
            const promises = files.map(async (f) => {
                const src = await readFileAsDataURL(f);
                return { type: 'image', src: src };
            });
            state.mediaItems = await Promise.all(promises);

            // UI Update for Images
            elements.inputMediaVideo.classList.add('hidden');
            elements.inputMediaVideo.src = ""; // Stop any playing video
            
            if (state.mediaItems.length > 0) {
                elements.inputMediaImg.src = state.mediaItems[0].src;
                elements.inputMediaImg.classList.remove('hidden');
                
                if (state.mediaItems.length > 1) {
                    elements.mediaCountOverlay.textContent = `+${state.mediaItems.length - 1}`;
                    elements.mediaCountOverlay.classList.remove('hidden');
                } else {
                    elements.mediaCountOverlay.classList.add('hidden');
                }
            }
        }

        elements.inputMediaPreview.classList.remove('hidden');
        updatePreview();
    });

    // Remove Media
    elements.removeMediaBtn.addEventListener('click', () => {
        elements.fileInput.value = '';
        state.mediaItems = [];
        state.rawFiles = [];
        elements.inputMediaPreview.classList.add('hidden');
        elements.inputMediaImg.src = '';
        elements.inputMediaVideo.src = '';
        updatePreview();
    });

    elements.caption.addEventListener('input', updatePreview);

    const openCreateModal = () => {
        loadPlatforms();
        elements.modal.classList.remove('hidden');
        setTimeout(() => {
            elements.modal.classList.remove('opacity-0');
            elements.content.classList.remove('scale-90');
            elements.content.classList.add('scale-100');
        }, 10);
        document.body.style.overflow = 'hidden';
    };

    // 2. Assign to all buttons
    elements.createBtn.addEventListener('click', openCreateModal);
    document.getElementById("Fcrtnew").addEventListener('click', openCreateModal);
    document.getElementById("NewTskCont").addEventListener('click', openCreateModal);
    document.getElementById("CrtNwInBtm").addEventListener('click',openCreateModal);

    


    function closeModal() {
        elements.modal.classList.add('opacity-0');
        elements.content.classList.remove('scale-100');
        elements.content.classList.add('scale-90');
        setTimeout(() => {
            elements.modal.classList.add('hidden');
            document.body.style.overflow = 'auto';
            resetForm();
        }, 300);
    }
    
    elements.closeBtn.addEventListener('click', closeModal);
    elements.modal.addEventListener('click', (e) => {
        if (e.target === elements.modal) closeModal();
    });

    function resetForm() {
        elements.caption.value = '';
        elements.fileInput.value = '';
        state.mediaItems = [];
        state.rawFiles = [];
        elements.inputMediaPreview.classList.add('hidden');
        updatePreview();
        elements.submitBtn.disabled = false;
        elements.submitBtn.textContent = 'Schedule Post';
        elements.submitBtn.classList.remove('bg-gray-400', 'cursor-not-allowed');
        elements.submitBtn.classList.add('bg-gray-900');
        elements.saveAsDraftBtn.textContent ='Save as draft'
        elements.saveAsDraftBtn.classList.remove('bg-gray-400', 'cursor-not-allowed');
        elements.saveAsDraftBtn.classList.add('bg-white');
    }

let messageIndex = 0;
const loadingMessages = [
    'Locking it in..',
    'Cooking..',
    'Sending fr..',
    'Almost ready..',
    'Sec..',
    'Finalizing..'
];

// 1. Reusable helper to handle the task submission
const handleTaskSubmission = (isDraft = false) => {
    if (!state.currentPlatform) return alert('Select a platform');
    if (!elements.caption.value || elements.caption.value.trim() === '') {
        ShowNoti('info', 'Please Fill The Caption');
        return;
    }

    // UI Feedback: Determine which button we are working with
    const btn = isDraft ? elements.saveAsDraftBtn : elements.submitBtn;
    const originalText = btn.textContent;
    const currentMsg = loadingMessages[messageIndex] || loadingMessages[loadingMessages.length - 1];

    if (messageIndex < loadingMessages.length - 1) messageIndex++;

    // Prepare Data
    const formData = new FormData();
    const now = new Date();
    const dateString = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const timeString = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    
    formData.append('title', `Task - ${dateString} ${timeString}`);
    formData.append('caption', elements.caption.value);
    formData.append('hashtags', document.getElementById('hashtagsMnl').value);
    formData.append('notes', document.getElementById('notesMnl').value);
    formData.append('status', isDraft ? 'draft' : 'published'); // Pass status to backend

    if (state.rawFiles.length > 0) {
        state.rawFiles.forEach(file => formData.append('files', file));
    }

    // Update UI to Loading State
    btn.disabled = true;
    btn.textContent = currentMsg;
    btn.classList.remove('bg-gray-900');
    btn.classList.add('bg-gray-400', 'cursor-not-allowed');

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/manual-tasks', true);

    xhr.addEventListener('load', () => {
        if (xhr.status === 200) {
            try {
                const response = JSON.parse(xhr.responseText);
                btn.textContent = isDraft ? 'Drafted' : 'Opening';
                setTimeout(() => {
                    closeModal();
                    // ONLY open detail if it's NOT a draft
                    if (!isDraft && typeof openDetail === 'function') {
                        openDetail(response.task_id);
                    }
                }, 1000);
            } catch (e) {
                btn.textContent = 'bad response.';
            }
            finally{
                fetchPostsBlz();
            }
        } else {
            handleError(btn);
        }
        
    });

    xhr.addEventListener('error', () => handleError(btn));
    xhr.send(formData);
};

const handleError = (btn) => {
    btn.textContent = 'try again.';
    btn.disabled = false;
    btn.classList.remove('bg-gray-400', 'cursor-not-allowed');
    btn.classList.add('bg-red-600');
};


elements.submitBtn.addEventListener('click', () => handleTaskSubmission(false));
elements.saveAsDraftBtn.addEventListener('click', () => handleTaskSubmission(true));

});