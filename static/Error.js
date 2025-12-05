 // Simple client-side state
 let currentPageErr = 1;
 const limitErr = 20;
 let totalErr = 127;
 let fromDateErr = '';
 let toDateErr = '';
 let searchTermErr = '';
 let filtersVisible = false;

 // Toggle filters visibility
 document.getElementById('toggleFiltersBtnErr').addEventListener('click', () => {
   filtersVisible = !filtersVisible;
   const filtersBar = document.getElementById('filtersBar');
   const icon = document.getElementById('filterIcon');
   
   if (filtersVisible) {
     filtersBar.classList.remove('hidden');
     icon.className = 'fas fa-chevron-up text-gray-500';
   } else {
     filtersBar.classList.add('hidden');
     icon.className = 'fas fa-chevron-down text-gray-400';
   }
 });

 // Show loading spinner in table
 function showLoadingErr() {
   const tbody = document.getElementById('errorLogsTbodyErr');
   tbody.innerHTML = `
     <tr>
       <td colspan="7" class="px-6 py-12 text-center">
       <div class="inline-flex items-center px-4 py-2 font-semibold leading-6 text-gray-600 transition ease-in-out duration-150 cursor-not-allowed">
       <svg class="animate-spin -ml-1 mr-3 h-7 w-7 text-gray-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
       <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
       <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
       </svg>
       Loading...
       </div>
       </td>
     </tr>
   `;
 }

 // Fetch logs from your FastAPI endpoint
 async function fetchErrorLogsErr() {
   showLoadingErr();

   const params = new URLSearchParams({
     limit: limitErr,
     offset: (currentPageErr - 1) * limitErr,
     ...(fromDateErr && { from_date: fromDateErr }),
     ...(toDateErr && { to_date: toDateErr })
   });

   try {
     const res = await fetch(`/error-logs?${params}`);
     const data = await res.json();

     let logs = data.error_logs;
     // Client-side search filter (since backend doesn't support yet)
     if (searchTermErr) {
       logs = logs.filter(log => 
         log.error_id.toLowerCase().includes(searchTermErr.toLowerCase()) ||
         (log.task_id || '').toLowerCase().includes(searchTermErr.toLowerCase()) ||
         (log.platform_id || '').toLowerCase().includes(searchTermErr.toLowerCase()) ||
         (log.error_type || '').toLowerCase().includes(searchTermErr.toLowerCase()) ||
         (log.message || '').toLowerCase().includes(searchTermErr.toLowerCase())
       );
     }

     renderTableErr(logs);
     totalErr = data.total;
     updatePaginationErr();
   } catch (err) {
     console.error("Failed to fetch error logs:", err);
     const tbody = document.getElementById('errorLogsTbodyErr');
     tbody.innerHTML = `
       <tr>
         <td colspan="7" class="px-6 py-12 text-center text-red-500 text-sm font-medium">Failed to load error logs. Please try again.</td>
       </tr>
     `;
   }
 }

 function formatDateErr(logDateStr) {
   const now = new Date();
   const logDate = new Date(logDateStr);
   const diffDays = Math.floor((now - logDate) / (1000 * 60 * 60 * 24));

   if (diffDays === 0) {
     // Today: show time only
     return logDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
   } else if (diffDays < 7) {
     // This week: show day abbr
     return logDate.toLocaleDateString('en-US', { weekday: 'short' });
   } else {
     // Else: full date
     return logDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
   }
 }

 function renderTableErr(logs) {
   const tbody = document.getElementById('errorLogsTbodyErr');
   if (logs.length === 0) {
     tbody.innerHTML = `
       <tr>
         <td colspan="7" class="px-6 py-8 text-center text-gray-500 text-sm font-medium">No error logs found matching your criteria</td>
       </tr>
     `;
     return;
   }

   tbody.innerHTML = logs.map(log => {
     const formattedDate = formatDateErr(log.created_at);

     const typeColor = log.error_type?.includes('Valid') ? 'bg-red-100 text-red-800' : 
                      log.error_type?.includes('Auth') ? 'bg-orange-100 text-orange-800' :
                      'bg-yellow-100 text-yellow-800';

     return `
       <tr class="hover:bg-gray-50 transition-colors duration-200">
         <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${log.error_id.substring(0, 6)}..</td>
         <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">${log.task_id.substring(0, 6) || '-'}</td>
         <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">${log.platform_id.substring(0, 6) || '-'}</td>
         <td class="px-6 py-4 whitespace-nowrap">
           <span class="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${typeColor}">
             ${log.error_type || 'Unknown'}
           </span>
         </td>
         <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">${log.error_code || '-'}</td>
         <td class="px-6 py-4 text-sm text-gray-700 max-w-xs truncate" title="${log.message || ''}">${log.message || '-'}</td>
         <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formattedDate}</td>
       </tr>
     `;
   }).join('');
 }

 function updatePaginationErr() {
   const start = ((currentPageErr - 1) * limitErr) + 1;
   const end = Math.min(currentPageErr * limitErr, totalErr);
   document.getElementById('pageInfoErr').textContent = start;
   document.getElementById('limitInfoErr').textContent = end;
   document.getElementById('totalCountErr').textContent = totalErr;

   const prevBtn = document.getElementById('prevPageBtnErr');
   const nextBtn = document.getElementById('nextPageBtnErr');
   prevBtn.disabled = currentPageErr === 1;
   nextBtn.disabled = end >= totalErr;
 }

 // Event Listeners
 document.getElementById('refreshBtnErr').addEventListener('click', () => {
   fetchErrorLogsErr();
 });

 document.getElementById('clearFiltersBtnErr').addEventListener('click', () => {
   document.getElementById('fromDateErr').value = '';
   document.getElementById('toDateErr').value = '';
   document.getElementById('searchInputErr').value = '';
   fromDateErr = '';
   toDateErr = '';
   searchTermErr = '';
   currentPageErr = 1;
   fetchErrorLogsErr();
 });

 document.getElementById('searchInputErr').addEventListener('input', (e) => {
   searchTermErr = e.target.value;
   currentPageErr = 1;
   fetchErrorLogsErr(); // Refetch with client-side filter
 });

 document.getElementById('fromDateErr').addEventListener('change', (e) => {
   fromDateErr = e.target.value ? new Date(e.target.value).toISOString() : '';
   currentPageErr = 1;
   fetchErrorLogsErr();
 });

 document.getElementById('toDateErr').addEventListener('change', (e) => {
   toDateErr = e.target.value ? new Date(e.target.value).toISOString() : '';
   currentPageErr = 1;
   fetchErrorLogsErr();
 });

 document.getElementById('prevPageBtnErr').addEventListener('click', () => {
   if (currentPageErr > 1) {
     currentPageErr--;
     fetchErrorLogsErr();
   }
 });

 document.getElementById('nextPageBtnErr').addEventListener('click', () => {
   if (currentPageErr * limitErr < totalErr) {
     currentPageErr++;
     fetchErrorLogsErr();
   }
 });

 // View details placeholder
 function viewDetailsErr(errorId) {
   alert(`Viewing details for ${errorId}`); // Replace with modal or redirect
 }

 // Initial load
 fetchErrorLogsErr();