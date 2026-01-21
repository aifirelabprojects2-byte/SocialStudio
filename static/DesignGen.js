let currentBatchId = null;
let selectedDesignIndex = 0;
let userTopic = "";
let canvasInstances = [];

function openPromptModal() {
document.getElementById("promptModal").classList.remove("hidden");
document.getElementById("promptInput").focus();
}

function closePromptModal() {
document.getElementById("promptModal").classList.add("hidden");
}

async function useSelectedDesign() {
// 1. Validation
if (!canvasInstances[selectedDesignIndex]) {
alert("No design selected or generated.");
return;
}

const btn = document.getElementById("useDesignBtn");
const originalText = btn.innerHTML;
btn.innerHTML = "Processing...";
btn.disabled = true;

try {
const canvas = canvasInstances[selectedDesignIndex];
const caption = document.getElementById("captionArea").value;
const currentWidth = canvas.getWidth();
const multiplier = 1080 / currentWidth;

// 3. Convert Canvas to Blob/File
const dataURL = canvas.toDataURL({
format: "png",
multiplier: multiplier,
quality: 1,
});

const res = await fetch(dataURL);
const blob = await res.blob();

const file = new File([blob], `ai-design-${Date.now()}.png`, {
type: "image/png",
});
if (window.loadAiDesignToModal) {
window.loadAiDesignToModal(file, caption);

document.getElementById("resultsView").classList.add("hidden");
} else {
console.error("Main script bridge not found");
}
} catch (error) {
console.error("Error processing design:", error);
alert("Failed to process design.");
} finally {
btn.innerHTML = originalText;
btn.disabled = false;
}
}

async function startGeneration() {
const prompt = document.getElementById("promptInput").value;
if (!prompt) return;
userTopic = prompt;

document.getElementById("resultsView").classList.remove("hidden");
document.getElementById("promptModal").classList.add("hidden");

renderSkeletons();

try {
const response = await fetch("/api/generate/design", {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({ prompt: prompt }),
});

if (!response.ok) throw new Error("API Error");
const data = await response.json();

currentBatchId = data.batch_id;

// Populate Data
document.getElementById("captionArea").value = data.caption || "";
renderGrid(data.designs);
} catch (error) {
console.error(error);
alert("We couldn't generate the designs. Please try again.");
window.location.reload();
}
}

function closeResultsView() {
const resultsView = document.getElementById("resultsView");
if (resultsView) {
resultsView.classList.add("hidden");
}
canvasInstances.forEach((canvas) => {
if (canvas && typeof canvas.dispose === "function") {
canvas.dispose();
}
});
canvasInstances = [];
currentBatchId = null;
selectedDesignIndex = 0;
const grid = document.getElementById("designsGrid");
if (grid) {
grid.innerHTML = "";
}
const captionArea = document.getElementById("captionArea");
if (captionArea) {
captionArea.value = "";
}
}

function renderSkeletons() {
const grid = document.getElementById("designsGrid");
grid.innerHTML = "";
for (let i = 0; i < 6; i++) {
grid.innerHTML += `
    <div class="space-y-4">
        <div class="canvas-wrapper skeleton h-[320px] rounded-xl border-0"></div>
        <div class="flex items-center gap-3 px-1">
                <div class="w-6 h-6 rounded-full bg-gray-100 skeleton"></div>
                <div class="h-2.5 bg-gray-100 rounded w-24 skeleton"></div>
        </div>
    </div>`;
}
}

function renderGrid(designs) {
const grid = document.getElementById("designsGrid");
grid.innerHTML = "";

designs.forEach((item, index) => {
const designId = item.id;

// 1. Card Container
const card = document.createElement("div");
card.className = `group cursor-pointer relative ${index === 0 ? "selected-card" : ""}`;

// Selection Logic
card.onclick = (e) => {
if (e.target.closest(".edit-btn")) return;
selectCard(card, index);
};

// 2. Canvas Wrapper
const wrapper = document.createElement("div");
wrapper.className =
"canvas-wrapper relative shadow-sm hover:shadow-md transition-shadow duration-300";

const inner = document.createElement("div");
inner.className = "canvas-inner";

const canvasId = `c-${index}`;
const canvasEl = document.createElement("canvas");
canvasEl.id = canvasId;
inner.appendChild(canvasEl);

// === HOVER EDIT BUTTON ===
const editOverlay = document.createElement("div");
editOverlay.className =
"absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center z-10 pointer-events-none rounded-xl";

const editBtn = document.createElement("a");
editBtn.href = `/canvas?template_id=${designId}`;
editBtn.target = "_blank";
editBtn.className =
"edit-btn pointer-events-auto bg-white/90 backdrop-blur text-gray-900 px-5 py-2 rounded-full text-xs font-bold shadow-lg hover:scale-105 transition transform flex items-center gap-2";
editBtn.innerHTML = `
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
    Edit Design
`;

editOverlay.appendChild(editBtn);
wrapper.appendChild(inner);
wrapper.appendChild(editOverlay);
card.appendChild(wrapper);

// 3. Meta Info
const meta = document.createElement("div");
meta.className = "flex items-center gap-2 mt-3 px-1";
meta.innerHTML = `
    <div class="w-5 h-5 rounded-full bg-gradient-to-tr from-gray-200 to-gray-300 flex items-center justify-center text-[9px] font-bold text-gray-600">AI</div>
    <span class="text-xs font-medium text-gray-500 group-hover:text-black ">Variation ${index + 1}</span>
`;
card.appendChild(meta);

grid.appendChild(card);

// Initialize Fabric Canvas
setTimeout(() => initCanvas(canvasId, item.design, wrapper), 50);
});
}

function initCanvas(id, json, wrapper) {
const canvas = new fabric.StaticCanvas(id);

// EXTRACT INDEX FROM ID (e.g., "c-0" -> 0)
const index = parseInt(id.split("-")[1]);
canvasInstances[index] = canvas; // <--- STORE INSTANCE

canvas.loadFromJSON(json, function () {
const targetW = 1080;
const targetH = 1350;
const containerW = wrapper.clientWidth;
const scale = containerW / targetW;

canvas.setDimensions({
width: containerW,
height: containerW * (targetH / targetW),
});

canvas.setZoom(scale);
canvas.renderAll();
});
}

function selectCard(element, index) {
document
.querySelectorAll(".selected-card")
.forEach((el) => el.classList.remove("selected-card"));
element.classList.add("selected-card");
selectedDesignIndex = index;
}

// --- CAPTION REGENERATION ---
async function regenerateCaption() {
if (!currentBatchId) return;

const btn = document.getElementById("regenCaptionBtn");
const shimmer = document.getElementById("captionShimmer");

btn.disabled = true;
shimmer.classList.remove("hidden");

try {
const response = await fetch("/api/regenerate/caption", {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({
    batch_id: currentBatchId,
    topic: userTopic,
}),
});

const data = await response.json();
document.getElementById("captionArea").value = data.caption;
} catch (error) {
console.error(error);
alert("Failed to regenerate caption.");
} finally {
btn.disabled = false;
shimmer.classList.add("hidden");
}
}

function openSaveModal() {
// Ensure a canvas is actually generated/selected
if (!canvasInstances[selectedDesignIndex]) {
alert("Please generate designs first.");
return;
}
document.getElementById("saveModal").classList.remove("hidden");
document.getElementById("save-name").focus();
}

function closeSaveModal() {
document.getElementById("saveModal").classList.add("hidden");
}

async function submitSaveTemplate() {
const nameInput = document.getElementById("save-name");
const name = nameInput.value;

if (!name) {
alert("Please enter a template name");
nameInput.focus();
return;
}

const btn = document.getElementById("saveSubmitBtn");
const originalBtnText = btn.innerHTML;
btn.innerHTML = `<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Saving...`;
btn.disabled = true;

try {
const canvas = canvasInstances[selectedDesignIndex];
const baseUrl = window.location.origin;
const projectData = canvas.toJSON([
"asset_type",
"server_id",
"selectable",
"evented",
"isFrame",
"frameOffsetX",
"frameOffsetY",
"clipPath",
"id",
"lockMovementX",
"lockMovementY",
"isBgRemoved",
"originalSrc",
]);

// 3. Fix Blob URLs dynamically
projectData.objects.forEach((obj) => {
const isMedia =
    obj.type === "image" ||
    obj.asset_type === "image" ||
    obj.asset_type === "video";
if (
    isMedia &&
    obj.server_id &&
    obj.src &&
    obj.src.startsWith("blob:")
) {
    obj.src = `${baseUrl}/uploads/${obj.server_id}`;
}
});

const json = JSON.stringify(projectData);

const currentWidth = canvas.getWidth();
const multiplier = 540 / currentWidth; // Target ~540px preview width
const dataURL = canvas.toDataURL({
format: "png",
multiplier: multiplier,
});
const blob = await (await fetch(dataURL)).blob();

// 5. Send to Backend
const fd = new FormData();
fd.append("name", name);
fd.append("type", document.getElementById("save-type").value);
fd.append("category", document.getElementById("save-category").value);
fd.append("style", document.getElementById("save-style").value);
fd.append("width", 1080);
fd.append("height", 1350);
fd.append("json_data", json);
fd.append("preview", blob, "preview.png");

const res = await fetch("/save-template", {
method: "POST",
body: fd,
});
const data = await res.json();

if (data.status === "success") {
closeSaveModal();
// Optional: Show a toast notification here instead of alert
alert("Template Saved Successfully!");
} else {
throw new Error(data.message || "Unknown error");
}
} catch (err) {
console.error(err);
alert("Error saving: " + err.message);
} finally {
btn.innerHTML = originalBtnText;
btn.disabled = false;
}
}