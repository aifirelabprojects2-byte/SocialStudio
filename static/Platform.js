const modalCreated = document.getElementById('createModal')
const tbody = document.getElementById('tbody')
const table = document.getElementById('table')
const PlatformEmptyState = document.getElementById('PlatformEmptyState')
const skeletonPlatform = document.getElementById('skeletonPlatform')
const form = document.getElementById('createForm')
const saveBtn = document.getElementById('saveBtn')


// Open modalCreated
document.getElementById('openModalBtn').onclick = () => modalCreated.showModal()
document.getElementById('openModalBtn2').onclick = () => modalCreated.showModal()
document.getElementById('cancelBtn').onclick = () => modalCreated.close()

async function loadPlatforms() {
  skeletonPlatform.classList.remove('hidden')
  table.classList.add('hidden')
  PlatformEmptyState.classList.add('hidden')

  try {
    const res = await fetch('/api/platforms')
    const platforms = await res.json()

    skeletonPlatform.classList.add('hidden')

    if (platforms.length === 0) {
      PlatformEmptyState.classList.remove('hidden')
      return
    }

    table.classList.remove('hidden')
    tbody.innerHTML = ''

    platforms.forEach(p => {
      const status = p.token_valid
        ? `<span class="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">Valid</span>`
        : `<span class="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">Invalid</span>`

      const row = document.createElement('tr')
      row.innerHTML = `
        <td class="px-6 py-4 font-medium text-gray-900">${p.name}</td>
        <td class="px-6 py-4 text-sm text-gray-500">${p.api_name || '—'}</td>
        <td class="px-6 py-4 text-sm font-mono">
          ${p.masked_token ? status + ' ' + p.masked_token : 'No token'}
        </td>
        <td class="px-6 py-4 text-sm text-gray-500">
          ${new Date(p.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
        </td>
        <td class="px-6 py-4 text-right">
          <button onclick="deletePlatform('${p.platform_id}', '${p.name.replace(/'/g, "\\'")}')"
                  class="text-red-600 hover:text-red-900 font-medium text-sm">Delete</button>
        </td>
      `
      tbody.appendChild(row)
    })
  } catch (err) {
    alert('Failed to load: ' + err.message)
    skeletonPlatform.classList.add('hidden')
  }
}

async function deletePlatform(id, name) {
  if (!confirm(`Delete "${name}"? This cannot be undone.`)) return
  try {
    const res = await fetch(`/api/platforms/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(await res.text())
    loadPlatforms()
  } catch (e) {
    alert('Delete failed: ' + e.message)
  }
}

form.onsubmit = async e => {
  e.preventDefault()
  saveBtn.disabled = true
  saveBtn.textContent = 'Saving...'

  const data = Object.fromEntries(new FormData(form))

  try {
    const res = await fetch('/api/platforms/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Failed to create')
    }

    modalCreated.close()
    form.reset()
    loadPlatforms()
    alert('Platform created successfully!')
  } catch (e) {
    alert('Error: ' + e.message)
  } finally {
    saveBtn.disabled = false
    saveBtn.textContent = 'Save Platform'
  }
}

// Refresh button
document.getElementById('refreshBtn').onclick = loadPlatforms


loadPlatforms()