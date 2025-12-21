async function loadSess() {
    const loadingSess = document.getElementById("loadingSess");
    const errorDivSess = document.getElementById("error");
    const errorText = document.getElementById("error-text");
    const emptyStateSes = document.getElementById("empty-state");
    const currentSectionSess = document.getElementById("current-session-section");
    const currentContainer = document.getElementById("current-session");
    const otherSection = document.getElementById("other-sessions-section");
    const otherContainer = document.getElementById("other-sessions");

    loadingSess.classList.remove("hidden");
    errorDivSess.classList.add("hidden");
    emptyStateSes.classList.add("hidden");
    currentSectionSess.classList.add("hidden");
    otherSection.classList.add("hidden");
    currentContainer.innerHTML = "";
    otherContainer.innerHTML = "";

    try {
        const response = await fetch(`/api/sessions`, { credentials: "include" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const sessions = await response.json();
        if (sessions.length === 0) {
            loadingSess.classList.add("hidden");
            emptyStateSes.classList.remove("hidden");
            return;
        }

        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
        }
        const currentToken = getCookie("session_token");

        let currentSession = null;
        const otherSessions = [];

        sessions.forEach(sess => {
            const isCurrent = sess.token && currentToken && sess.token === currentToken;
            const lastSeen = new Date(sess.last_seen_at);
            const now = new Date();
            const isVeryRecent = (now - lastSeen) < 60000; 

            if (isCurrent || (!currentSession && isVeryRecent)) {
                currentSession = sess;
            } else {
                otherSessions.push(sess);
            }
        });


        if (currentSession) {
            const ua = (currentSession.user_agent || "").toLowerCase();
            let deviceName = "Desktop";
            let icon = "monitor";          
            let browser = "Web Browser";
            let os = "Unknown OS";

            if (ua.includes("iphone")) { 
                deviceName = "iPhone"; 
                icon = "smartphone"; 
                os = "iOS"; 
                browser = "Safari"; 
            }
            else if (ua.includes("ipad")) { 
                deviceName = "iPad"; 
                icon = "tablet";             
                os = "iPadOS"; 
                browser = "Safari"; 
            }
            else if (ua.includes("android")) { 
                deviceName = "Android Device"; 
                icon = "smartphone"; 
                os = "Android"; 
                browser = "Chrome"; 
            }
            else if (ua.includes("mac")) { 
                deviceName = "Mac"; 
                icon = "laptop-2";           
                os = "macOS"; 
                browser = "Chrome/Safari"; 
            }
            else if (ua.includes("windows")) { 
                deviceName = "Windows PC"; 
                icon = "laptop-2";        
                os = "Windows"; 
                browser = "Chrome/Edge"; 
            }

            currentContainer.innerHTML = `
                <div class="flex flex-col md:flex-row gap-6 items-center p-6 bg-white rounded-xl border border-gray-200">
                    <div class="size-20 rounded-2xl bg-gray-100 flex items-center justify-center shrink-0 text-slate-700 relative overflow-hidden border border-gray-300">
                        <!-- Lucide icon instead of Material Symbols -->
                        <i data-lucide="${icon}" class="w-10 h-10 relative z-10"></i>
                        
                        <!-- Status dot remains unchanged -->
                        <span class="absolute top-2 right-2 flex h-3 w-3">
                            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-gray-500 opacity-75"></span>
                            <span class="relative inline-flex rounded-full h-3 w-3 bg-gray-600 border-2 border-white"></span>
                        </span>
                    </div>
                    <div class="flex-1 text-center md:text-left space-y-1">
                        <h3 class="text-xl font-bold text-slate-900">${deviceName}</h3>
                        <p class="text-sm font-medium text-slate-500">
                            ${currentSession.location || "Unknown Location"} • ${currentSession.ip_address || "Unknown IP"}
                        </p>
                        <div class="flex items-center justify-center md:justify-start gap-2 pt-2">
                            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-gray-50 border border-gray-300 text-xs text-slate-600 font-medium">
                                ${browser}
                            </span>
                            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-gray-50 border border-gray-300 text-xs text-slate-600 font-medium">
                                <i data-lucide="laptop-minimal-check" class="w-4 h-4"></i>
                                ${os}
                            </span>
                        </div>
                    </div>
                    <div class="md:pl-6 md:border-l border-gray-300 flex flex-col items-center gap-2 min-w-[140px]">
                        <span class="text-xs font-semibold text-slate-800 bg-gray-200 px-3 py-1 rounded-full">This Device</span>
                        <span class="text-[10px] text-slate-400">Last accessed: Just now</span>
                    </div>
                </div>
            `;

  
            lucide.createIcons();

            currentSectionSess.classList.remove("hidden");
        }

        if (otherSessions.length > 0) {
            otherSessions.forEach(sess => {
                const ua = (sess.user_agent || "").toLowerCase();
                let deviceName = "Unknown Device";
                let icon = "monitor"; 
                let os = "Unknown OS";
                let browser = "Unknown Browser";
        
                if (ua.includes("iphone")) { 
                    deviceName = "iPhone"; 
                    icon = "smartphone"; 
                    os = "iOS"; 
                    browser = "Safari"; 
                }
                else if (ua.includes("ipad")) { 
                    deviceName = "iPad"; 
                    icon = "tablet";             
                    os = "iPadOS"; 
                    browser = "Safari"; 
                }
                else if (ua.includes("android")) { 
                    deviceName = "Android Device"; 
                    icon = "smartphone"; 
                    os = "Android"; 
                    browser = "Chrome"; 
                }
                else if (ua.includes("mac")) { 
                    deviceName = "Mac"; 
                    icon = "laptop-2";           
                    os = "macOS"; 
                    browser = "Chrome/Safari"; 
                }
                else if (ua.includes("windows")) { 
                    deviceName = "Windows PC"; 
                    icon = "laptop-2";        
                    os = "Windows"; 
                    browser = "Chrome/Edge"; 
                }
        
                const lastActive = timeAgo(sess.last_seen_at);
        
                const item = document.createElement("div");
                item.className = "group bg-white rounded-2xl p-5 shadow-card hover:shadow-soft transition-all duration-300 border border-gray-200 hover:border-gray-300 flex flex-col md:flex-row items-center gap-5";
                item.innerHTML = `
                    <div class="size-14 rounded-xl bg-gray-100 text-slate-500 group-hover:bg-gray-200 group-hover:text-slate-700 flex items-center justify-center shrink-0 transition-colors border border-gray-300">
                        <i data-lucide="${icon}" class="w-8 h-8"></i> <!-- Slightly smaller than main device card -->
                    </div>
                    <div class="flex-1 min-w-0 text-center md:text-left">
                        <h4 class="text-base font-bold text-slate-900 mb-1">${deviceName}</h4>
                        <div class="text-sm text-slate-500">
                            ${sess.location || "Unknown Location"} • Active ${lastActive}
                        </div>
                        <div class="flex justify-center md:justify-start gap-2 mt-3">
                            <span class="text-[10px] bg-gray-50 border border-gray-300 px-2 py-0.5 rounded text-slate-600">${os}</span>
                            <span class="text-[10px] bg-gray-50 border border-gray-300 px-2 py-0.5 rounded text-slate-600">${browser}</span>
                        </div>
                    </div>
                    <button onclick="logoutSession('${sess.session_id}')" class="w-full md:w-auto px-5 py-2.5 rounded-xl border border-gray-400 text-slate-700 hover:text-slate-900 hover:border-gray-500 hover:bg-gray-50 text-sm font-semibold transition-all flex items-center justify-center gap-2">
                        <i data-lucide="log-out" class="w-5 h-5"></i>
                        <span>Log out</span>
                    </button>
                `;
                otherContainer.appendChild(item);
            });

            lucide.createIcons();
        
            otherSection.classList.remove("hidden");
        }

        loadingSess.classList.add("hidden");

    } catch (err) {
        errorText.textContent = "Some Error Occured, Try Again Later";
        errorDivSess.classList.remove("hidden");
        loadingSess.classList.add("hidden");
    }
}

function timeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    let interval = seconds / 86400;
    if (interval > 1) return Math.floor(interval) + " days ago";
    interval = seconds / 3600;
    if (interval > 1) return Math.floor(interval) + " hours ago";
    interval = seconds / 60;
    if (interval > 1) return Math.floor(interval) + " minutes ago";
    return "just now";
}

async function logoutSession(sessionId) {
    if (!confirm("Are you sure you want to log out this device?")) return;

    try {
        const response = await fetch(`/sessions/${sessionId}/logout`, {
            method: "POST",
            credentials: "include"
        });

        if (response.ok || response.redirected) {
            loadSess();
            if (response.redirected && response.url.includes("/login")) {
                setTimeout(() => window.location.href = "/login", 1000);
            }
        } else {
            throw new Error("Failed to revoke session");
        }
    } catch (err) {
        alert("Error: " + err.message);
    }
}

window.onload = loadSess;
