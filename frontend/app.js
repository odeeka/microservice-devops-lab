// Global state
let apiUrl = 'http://localhost:8000';
let accessToken = null;
let currentUser = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check for existing session
    const savedToken = localStorage.getItem('accessToken');
    const savedApiUrl = localStorage.getItem('apiUrl');
    const savedUser = localStorage.getItem('currentUser');
    
    if (savedToken && savedUser) {
        accessToken = savedToken;
        apiUrl = savedApiUrl || 'http://localhost:8000';
        currentUser = JSON.parse(savedUser);
        showDashboard();
    }
    
    // Event listeners
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    document.getElementById('logoutBtn').addEventListener('click', handleLogout);
    
    // Navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.getAttribute('data-view');
            switchView(view);
        });
    });
    
    // Filters and search
    document.getElementById('userSearch').addEventListener('input', debounce(loadUsers, 500));
    document.getElementById('roleFilter').addEventListener('change', loadUsers);
    document.getElementById('activeOnlyFilter').addEventListener('change', loadUsers);
    document.getElementById('activeSessionsOnly').addEventListener('change', loadSessions);
});

// Authentication
async function handleLogin(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    apiUrl = document.getElementById('apiUrl').value;
    
    const errorDiv = document.getElementById('loginError');
    errorDiv.style.display = 'none';
    
    try {
        const response = await fetch(`${apiUrl}/api/v1/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        if (!response.ok) {
            throw new Error('Invalid credentials or API not reachable');
        }
        
        const data = await response.json();
        accessToken = data.access_token;
        
        // Get user info
        const userResponse = await fetch(`${apiUrl}/api/v1/auth/me`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        currentUser = await userResponse.json();
        
        // Check if user is admin
        if (currentUser.role !== 'admin') {
            throw new Error('Access denied. Admin role required.');
        }
        
        // Save to localStorage
        localStorage.setItem('accessToken', accessToken);
        localStorage.setItem('apiUrl', apiUrl);
        localStorage.setItem('currentUser', JSON.stringify(currentUser));
        
        showDashboard();
    } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.style.display = 'block';
    }
}

function handleLogout() {
    // Clear storage
    localStorage.removeItem('accessToken');
    localStorage.removeItem('apiUrl');
    localStorage.removeItem('currentUser');
    
    accessToken = null;
    currentUser = null;
    
    // Show login screen
    document.getElementById('loginScreen').style.display = 'flex';
    document.getElementById('dashboardScreen').style.display = 'none';
    
    // Optional: Call logout endpoint
    fetch(`${apiUrl}/api/v1/auth/logout`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${accessToken}`
        }
    }).catch(() => {});
}

function showDashboard() {
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('dashboardScreen').style.display = 'flex';
    document.getElementById('userInfo').textContent = `👤 ${currentUser.username} (${currentUser.role})`;
    
    // Load initial data
    loadOverview();
}

// View Navigation
function switchView(viewName) {
    // Update active nav button
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-view="${viewName}"]`).classList.add('active');
    
    // Update active view
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(`${viewName}View`).classList.add('active');
    
    // Load view data
    switch(viewName) {
        case 'overview':
            loadOverview();
            break;
        case 'users':
            loadUsers();
            break;
        case 'sessions':
            loadSessions();
            break;
        case 'security':
            loadSuspiciousLogins();
            break;
        case 'activity':
            loadActivity();
            break;
    }
}

// API Calls
async function apiCall(endpoint, options = {}) {
    const response = await fetch(`${apiUrl}${endpoint}`, {
        ...options,
        headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
            ...options.headers
        }
    });
    
    if (response.status === 401) {
        handleLogout();
        throw new Error('Session expired. Please login again.');
    }
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'API request failed');
    }
    
    return response.json();
}

// Overview
async function loadOverview() {
    try {
        const data = await apiCall('/api/v1/admin/dashboard/overview');
        
        // Update stats
        document.getElementById('totalUsers').textContent = data.users.total;
        document.getElementById('activeUsers').textContent = data.users.active;
        document.getElementById('activeSessions').textContent = data.sessions.active;
        document.getElementById('suspiciousLogins').textContent = data.security.suspicious_logins_7d;
        
        // Users by role
        const roleStats = document.getElementById('usersByRole');
        roleStats.innerHTML = '';
        for (const [role, count] of Object.entries(data.users.by_role)) {
            roleStats.innerHTML += `
                <div class="role-item">
                    <span class="role-label">${role.charAt(0).toUpperCase() + role.slice(1)}</span>
                    <span class="role-value">${count}</span>
                </div>
            `;
        }
        
        // Recent stats
        const recentStats = document.getElementById('recentStats');
        recentStats.innerHTML = `
            <div class="activity-item">
                <span class="activity-label">Logins (24h)</span>
                <span class="activity-value">${data.security.logins_24h}</span>
            </div>
            <div class="activity-item">
                <span class="activity-label">Revoked Sessions</span>
                <span class="activity-value">${data.sessions.revoked}</span>
            </div>
            <div class="activity-item">
                <span class="activity-label">Expired Sessions</span>
                <span class="activity-value">${data.sessions.expired}</span>
            </div>
            <div class="activity-item">
                <span class="activity-label">Blacklisted Tokens</span>
                <span class="activity-value">${data.security.blacklisted_tokens}</span>
            </div>
        `;
    } catch (error) {
        console.error('Error loading overview:', error);
    }
}

function refreshOverview() {
    loadOverview();
}

// Users
async function loadUsers() {
    const search = document.getElementById('userSearch').value;
    const role = document.getElementById('roleFilter').value;
    const activeOnly = document.getElementById('activeOnlyFilter').checked;
    
    const params = new URLSearchParams({
        limit: 100,
        skip: 0
    });
    
    if (search) params.append('search', search);
    if (role) params.append('role', role);
    if (activeOnly) params.append('active_only', 'true');
    
    try {
        const users = await apiCall(`/api/v1/admin/users?${params}`);
        
        const tbody = document.getElementById('usersTableBody');
        
        if (users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="loading">No users found</td></tr>';
            return;
        }
        
        tbody.innerHTML = users.map(user => `
            <tr>
                <td>${user.id}</td>
                <td><strong>${user.username}</strong></td>
                <td>${user.email}</td>
                <td>${user.full_name || '-'}</td>
                <td><span class="badge ${user.role}">${user.role}</span></td>
                <td><span class="badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Active' : 'Inactive'}</span></td>
                <td>${formatDate(user.created_at)}</td>
                <td>
                    <button class="btn btn-success" onclick="viewUser(${user.id})">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${user.is_active ? 
                        `<button class="btn btn-warning" onclick="deactivateUser(${user.id}, '${user.username}')">
                            <i class="fas fa-ban"></i>
                        </button>` :
                        `<button class="btn btn-success" onclick="activateUser(${user.id}, '${user.username}')">
                            <i class="fas fa-check"></i>
                        </button>`
                    }
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

async function viewUser(userId) {
    try {
        const user = await apiCall(`/api/v1/admin/users/${userId}`);
        
        const modalBody = document.getElementById('userModalBody');
        modalBody.innerHTML = `
            <div class="user-detail-item">
                <span class="user-detail-label">ID:</span>
                <span class="user-detail-value">${user.id}</span>
            </div>
            <div class="user-detail-item">
                <span class="user-detail-label">Username:</span>
                <span class="user-detail-value">${user.username}</span>
            </div>
            <div class="user-detail-item">
                <span class="user-detail-label">Email:</span>
                <span class="user-detail-value">${user.email}</span>
            </div>
            <div class="user-detail-item">
                <span class="user-detail-label">Full Name:</span>
                <span class="user-detail-value">${user.full_name || '-'}</span>
            </div>
            <div class="user-detail-item">
                <span class="user-detail-label">Role:</span>
                <span class="user-detail-value"><span class="badge ${user.role}">${user.role}</span></span>
            </div>
            <div class="user-detail-item">
                <span class="user-detail-label">Status:</span>
                <span class="user-detail-value"><span class="badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Active' : 'Inactive'}</span></span>
            </div>
            <div class="user-detail-item">
                <span class="user-detail-label">Verified:</span>
                <span class="user-detail-value">${user.is_verified ? '✅ Yes' : '❌ No'}</span>
            </div>
            <div class="user-detail-item">
                <span class="user-detail-label">Created:</span>
                <span class="user-detail-value">${formatDate(user.created_at)}</span>
            </div>
            <div class="user-detail-item">
                <span class="user-detail-label">Updated:</span>
                <span class="user-detail-value">${formatDate(user.updated_at)}</span>
            </div>
        `;
        
        document.getElementById('userModal').classList.add('active');
    } catch (error) {
        alert('Error loading user details: ' + error.message);
    }
}

function closeUserModal() {
    document.getElementById('userModal').classList.remove('active');
}

async function deactivateUser(userId, username) {
    if (!confirm(`Are you sure you want to deactivate user "${username}"?`)) {
        return;
    }
    
    try {
        await apiCall(`/api/v1/admin/users/${userId}/deactivate`, {
            method: 'POST',
            body: JSON.stringify({
                reason: 'Deactivated by admin',
                revoke_sessions: true
            })
        });
        
        alert('User deactivated successfully');
        loadUsers();
    } catch (error) {
        alert('Error deactivating user: ' + error.message);
    }
}

async function activateUser(userId, username) {
    if (!confirm(`Are you sure you want to reactivate user "${username}"?`)) {
        return;
    }
    
    try {
        await apiCall(`/api/v1/admin/users/${userId}/activate`, {
            method: 'POST'
        });
        
        alert('User reactivated successfully');
        loadUsers();
    } catch (error) {
        alert('Error activating user: ' + error.message);
    }
}

// Sessions
async function loadSessions() {
    const activeOnly = document.getElementById('activeSessionsOnly').checked;
    
    const params = new URLSearchParams({
        active_only: activeOnly,
        limit: 100
    });
    
    try {
        const data = await apiCall(`/api/v1/admin/sessions/all?${params}`);
        const sessions = data.sessions || [];
        
        const tbody = document.getElementById('sessionsTableBody');
        
        if (sessions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="loading">No sessions found</td></tr>';
            return;
        }
        
        tbody.innerHTML = sessions.map(session => `
            <tr>
                <td>${session.session_id}</td>
                <td><strong>${session.username}</strong></td>
                <td>${session.device}</td>
                <td>${session.ip_address}</td>
                <td>${formatDate(session.created_at)}</td>
                <td>${formatDate(session.last_active)}</td>
                <td><span class="risk-score ${getRiskClass(session.risk_score)}">${session.risk_score}</span></td>
                <td><span class="badge ${session.is_revoked ? 'revoked' : 'active'}">${session.is_revoked ? 'Revoked' : 'Active'}</span></td>
                <td>
                    ${!session.is_revoked ? 
                        `<button class="btn btn-danger" onclick="revokeSession(${session.session_id})">
                            <i class="fas fa-ban"></i>
                        </button>` :
                        '-'
                    }
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

async function revokeSession(sessionId) {
    if (!confirm(`Are you sure you want to revoke session ${sessionId}?`)) {
        return;
    }
    
    try {
        await apiCall(`/api/v1/admin/sessions/${sessionId}`, {
            method: 'DELETE'
        });
        
        alert('Session revoked successfully');
        loadSessions();
    } catch (error) {
        alert('Error revoking session: ' + error.message);
    }
}

// Security
async function loadSuspiciousLogins() {
    const days = document.getElementById('securityDays').value;
    const minRiskScore = document.getElementById('minRiskScore').value;
    
    const params = new URLSearchParams({
        days: days,
        min_risk_score: minRiskScore
    });
    
    try {
        const data = await apiCall(`/api/v1/admin/security/suspicious-logins?${params}`);
        const logins = data.suspicious_logins || [];
        
        const tbody = document.getElementById('securityTableBody');
        
        if (logins.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="loading">No suspicious logins found</td></tr>';
            return;
        }
        
        tbody.innerHTML = logins.map(login => `
            <tr>
                <td>${login.session_id}</td>
                <td><strong>${login.username}</strong></td>
                <td>${login.device}</td>
                <td>${login.ip_address}</td>
                <td>${formatDate(login.timestamp)}</td>
                <td><span class="risk-score ${getRiskClass(login.risk_score)}">${login.risk_score}</span></td>
                <td>${login.risk_factors ? login.risk_factors.join(', ') : '-'}</td>
                <td>${login.recommendation || '-'}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading suspicious logins:', error);
    }
}

// Activity
async function loadActivity() {
    const hours = document.getElementById('activityHours').value;
    
    try {
        const data = await apiCall(`/api/v1/admin/dashboard/activity?hours=${hours}`);
        
        // Recent logins
        const loginsDiv = document.getElementById('recentLogins');
        const logins = data.recent_logins || [];
        
        if (logins.length === 0) {
            loginsDiv.innerHTML = '<p style="color: var(--text-secondary); padding: 12px;">No recent logins</p>';
        } else {
            loginsDiv.innerHTML = logins.map(login => `
                <div class="activity-item">
                    <strong>${login.username}</strong> logged in
                    <small>${login.device} • ${login.ip_address}</small>
                    <small>${formatDate(login.timestamp)} • Risk: <span class="${getRiskClass(login.risk_score)}">${login.risk_score}</span></small>
                </div>
            `).join('');
        }
        
        // Recent revocations
        const revocationsDiv = document.getElementById('recentRevocations');
        const revocations = data.recent_revocations || [];
        
        if (revocations.length === 0) {
            revocationsDiv.innerHTML = '<p style="color: var(--text-secondary); padding: 12px;">No recent revocations</p>';
        } else {
            revocationsDiv.innerHTML = revocations.map(rev => `
                <div class="activity-item">
                    <strong>${rev.username}</strong> session revoked
                    <small>${rev.device}</small>
                    <small>${formatDate(rev.revoked_at)} • ${rev.reason}</small>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading activity:', error);
    }
}

// Utility Functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getRiskClass(score) {
    if (score >= 70) return 'risk-high';
    if (score >= 40) return 'risk-medium';
    return 'risk-low';
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
