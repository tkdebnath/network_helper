const API_BASE = '/api';

async function fetchPrechecks() {
    const deviceName = document.getElementById('deviceName').value;
    if (!deviceName) {
        alert("Please enter a device name");
        return;
    }

    try {
        // alert(`Fetching prechecks for ${deviceName}...`); // Debug
        const response = await fetch(`${API_BASE}/prechecks/${deviceName}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const files = await response.json();
        // alert(`Found ${files.length} files.`); // Debug

        if (files.length === 0) {
            alert("No files found for this device.");
        }

        const list = document.getElementById('precheckList');
        list.innerHTML = files.map(file => `
            <li>
                <input type="checkbox" name="precheckFile" value="${file}" onchange="handleFileSelection()">
                ${file} 
                <a href="${API_BASE}/prechecks/download/${file}" download>[Download]</a>
            </li>
        `).join('');

        document.getElementById('precheckListContainer').style.display = 'block';

        const actionsDiv = document.getElementById('precheckActions');
        if (files.length > 1) {
            actionsDiv.style.display = 'block';
        } else {
            actionsDiv.style.display = 'none';
        }

        // Reset selection state
        handleFileSelection();
    } catch (e) {
        console.error("Failed to fetch prechecks", e);
        alert(`Failed to fetch prechecks: ${e.message}`);
    }
}

function handleFileSelection() {
    const checkboxes = document.querySelectorAll('input[name="precheckFile"]');
    const checkedCount = document.querySelectorAll('input[name="precheckFile"]:checked').length;

    checkboxes.forEach(cb => {
        if (!cb.checked) {
            cb.disabled = checkedCount >= 2;
        }
    });
}

async function compareFiles() {
    const checkboxes = document.querySelectorAll('input[name="precheckFile"]:checked');
    if (checkboxes.length !== 2) {
        alert("Please select exactly two files to compare.");
        return;
    }

    const file1 = checkboxes[0].value;
    const file2 = checkboxes[1].value;

    try {
        const response = await fetch(`${API_BASE}/prechecks/diff`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file1, file2 })
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`Server error: ${response.status} - ${errText}`);
        }

        const html = await response.text();
        const win = window.open("", "_blank");

        if (!win) {
            alert("Please allow popups for this site to view the comparison.");
            return;
        }

        // Inject download button
        const downloadBtnHtml = `
            <div style="position: fixed; top: 10px; right: 10px; z-index: 1000; background: white; padding: 10px; border: 1px solid #ccc; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
                <button onclick="downloadDiff()" style="padding: 8px 16px; background: #007bff; color: white; border: none; cursor: pointer; border-radius: 4px;">Download Report</button>
            </div>
            <script>
                function downloadDiff() {
                    const htmlContent = document.documentElement.outerHTML;
                    const blob = new Blob([htmlContent], {type: 'text/html'});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'diff_report.html';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                }
            </script>
        `;

        // Insert after body tag if present, otherwise prepend
        let finalHtml = html;
        if (finalHtml.includes('<body')) {
            finalHtml = finalHtml.replace(/<body[^>]*>/, match => match + downloadBtnHtml);
        } else {
            finalHtml = downloadBtnHtml + finalHtml;
        }

        win.document.write(finalHtml);
    } catch (e) {
        console.error("Diff failed", e);
        alert(`Failed to compare files: ${e.message}`);
    }
}

let fullHistory = [];
let currentPage = 1;
const itemsPerPage = 10;

async function refreshData() {
    // Fetch Queue
    try {
        const qRes = await fetch(`${API_BASE}/queue`);
        const queue = await qRes.json();
        const queueList = document.getElementById('queueList');
        queueList.innerHTML = queue.map(item => `<li>${item.device_name} - ${item.status}</li>`).join('') || '<li>No items in queue</li>';
    } catch (e) {
        console.error("Failed to fetch queue", e);
    }

    // Fetch History
    try {
        const hRes = await fetch(`${API_BASE}/history`);
        fullHistory = await hRes.json();
        renderHistory();
    } catch (e) {
        console.error("Failed to fetch history", e);
    }
}

function renderHistory() {
    const filterDevice = document.getElementById('filterDevice').value.toLowerCase();
    const filterStatus = document.getElementById('filterStatus').value;

    const filtered = fullHistory.filter(item => {
        const matchesDevice = item.device_name.toLowerCase().includes(filterDevice);
        const matchesStatus = filterStatus === 'all' || item.status === filterStatus;
        return matchesDevice && matchesStatus;
    });

    // Pagination Logic
    const totalPages = Math.ceil(filtered.length / itemsPerPage) || 1;
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const paginatedItems = filtered.slice(start, end);

    const tbody = document.querySelector('#historyTable tbody');
    tbody.innerHTML = paginatedItems.map(item => `
        <tr>
            <td>${item.task_id.substring(0, 8)}...</td>
            <td>${item.device_name}</td>
            <td>${item.status}</td>
            <td>${new Date(item.updated_at).toLocaleString()}</td>
            <td><button onclick="viewLogs('${item.task_id}')">Logs</button></td>
        </tr>
    `).join('');

    // Update Pagination Controls
    document.getElementById('pageIndicator').textContent = `Page ${currentPage} of ${totalPages}`;
    document.getElementById('prevPage').disabled = currentPage === 1;
    document.getElementById('nextPage').disabled = currentPage === totalPages;
}

function changePage(delta) {
    currentPage += delta;
    renderHistory();
}

// Reset page when filters change
document.getElementById('filterDevice').addEventListener('input', () => { currentPage = 1; renderHistory(); });
document.getElementById('filterStatus').addEventListener('change', () => { currentPage = 1; renderHistory(); });

async function viewLogs(taskId) {
    try {
        const response = await fetch(`${API_BASE}/status/${taskId}`);
        const data = await response.json();
        document.getElementById('logContent').textContent = data.log_output || "No logs available yet.";
        document.getElementById('logModal').style.display = "block";
    } catch (e) {
        alert("Failed to fetch logs");
    }
}

function closeModal() {
    document.getElementById('logModal').style.display = "none";
}

// Auto refresh every 5 seconds
setInterval(refreshData, 5000);
refreshData();

async function fetchDeviceSuggestions() {
    try {
        const response = await fetch(`${API_BASE}/prechecks/devices`);
        if (response.ok) {
            const devices = await response.json();
            const datalist = document.getElementById('deviceSuggestions');
            datalist.innerHTML = devices.map(device => `<option value="${device}">`).join('');
        }
    } catch (e) {
        console.error("Failed to fetch device suggestions", e);
    }
}

fetchDeviceSuggestions();
