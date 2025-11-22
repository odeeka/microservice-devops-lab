// Global state
let apiUrl = 'http://localhost:8000';
let accessToken = null;
let currentUser = null;
let currentEditItemId = null;
let cart = []; // Shopping cart

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check for existing session
    const savedToken = localStorage.getItem('accessToken');
    const savedApiUrl = localStorage.getItem('apiUrl');
    const savedUser = localStorage.getItem('currentUser');
    const savedCart = localStorage.getItem('cart');
    
    if (savedToken && savedUser) {
        accessToken = savedToken;
        apiUrl = savedApiUrl || 'http://localhost:8000';
        currentUser = JSON.parse(savedUser);
        cart = savedCart ? JSON.parse(savedCart) : [];
        updateCartBadge();
        showApp();
    }
    
    // Event listeners
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    document.getElementById('logoutBtn').addEventListener('click', handleLogout);
    document.getElementById('itemForm').addEventListener('submit', handleItemSubmit);
    
    // Filters and search
    document.getElementById('itemSearch').addEventListener('input', debounce(loadItems, 500));
    document.getElementById('categoryFilter').addEventListener('change', loadItems);
    document.getElementById('activeOnlyFilter').addEventListener('change', loadItems);
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
        
        // Save to localStorage
        localStorage.setItem('accessToken', accessToken);
        localStorage.setItem('apiUrl', apiUrl);
        localStorage.setItem('currentUser', JSON.stringify(currentUser));
        
        showApp();
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
    document.getElementById('appScreen').style.display = 'none';
    
    // Optional: Call logout endpoint
    fetch(`${apiUrl}/api/v1/auth/logout`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${accessToken}`
        }
    }).catch(() => {});
}

function showApp() {
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('appScreen').style.display = 'flex';
    document.getElementById('userInfo').textContent = `👤 ${currentUser.username} (${currentUser.role})`;
    
    // Load initial data
    loadStats();
    loadCategories();
    loadItems();
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
    
    // Handle 204 No Content (e.g., DELETE requests)
    if (response.status === 204) {
        return null;
    }
    
    if (!response.ok) {
        // Try to parse error JSON, fallback to status text
        try {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        } catch (e) {
            throw new Error(`API request failed: ${response.statusText}`);
        }
    }
    
    // Parse response body if present
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        return response.json();
    }
    
    return null;
}

// Load Stats
async function loadStats() {
    try {
        const stats = await apiCall('/api/v1/stats');
        
        document.getElementById('totalItems').textContent = stats.total_items || 0;
        document.getElementById('activeItems').textContent = stats.active_items || 0;
        document.getElementById('categoriesCount').textContent = stats.total_categories || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load Categories
async function loadCategories() {
    try {
        const categories = await apiCall('/api/v1/categories');
        
        const select = document.getElementById('categoryFilter');
        select.innerHTML = '<option value="">All Categories</option>';
        
        categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat;
            option.textContent = cat;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

// Load Items
async function loadItems() {
    const search = document.getElementById('itemSearch').value;
    const category = document.getElementById('categoryFilter').value;
    const activeOnly = document.getElementById('activeOnlyFilter').checked;
    
    const params = new URLSearchParams({
        limit: 100,
        skip: 0
    });
    
    if (search) params.append('search', search);
    if (category) params.append('category', category);
    if (activeOnly) params.append('active_only', 'true');
    
    try {
        const items = await apiCall(`/api/v1/items?${params}`);
        
        const grid = document.getElementById('itemsGrid');
        
        if (items.length === 0) {
            grid.innerHTML = '<div class="empty-message"><i class="fas fa-box-open"></i><p>No items found</p></div>';
            return;
        }
        
        grid.innerHTML = items.map(item => `
            <div class="item-card ${!item.is_active ? 'inactive' : ''}">
                <div class="item-header">
                    <h3>${escapeHtml(item.name)}</h3>
                    <span class="item-status ${item.is_active ? 'active' : 'inactive'}">
                        ${item.is_active ? '✓ Active' : '✗ Inactive'}
                    </span>
                </div>
                <div class="item-body">
                    <p class="item-description">${escapeHtml(item.description || 'No description')}</p>
                    <div class="item-meta">
                        <span class="item-price">$${parseFloat(item.price).toFixed(2)}</span>
                        <span class="item-category">
                            <i class="fas fa-tag"></i> ${escapeHtml(item.category)}
                        </span>
                        <span class="item-quantity" title="Available quantity">
                            <i class="fas fa-box"></i> ${item.quantity || 0} in stock
                        </span>
                    </div>
                    <div class="item-footer">
                        <small>Created: ${formatDate(item.created_at)}</small>
                    </div>
                </div>
                <div class="item-actions">
                    <button class="btn btn-sm btn-success" onclick='addToCart(${JSON.stringify(item)})'>
                        <i class="fas fa-cart-plus"></i> Add to Cart
                    </button>
                    <button class="btn btn-sm btn-info" onclick="viewItem(${item.id})">
                        <i class="fas fa-eye"></i> View
                    </button>
                    <button class="btn btn-sm btn-primary" onclick="editItem(${item.id})">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteItem(${item.id}, '${escapeHtml(item.name)}')">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading items:', error);
        document.getElementById('itemsGrid').innerHTML = 
            '<div class="error-message">Error loading items. Please try again.</div>';
    }
}

// View Item
async function viewItem(itemId) {
    try {
        const item = await apiCall(`/api/v1/items/${itemId}`);
        
        const modalBody = document.getElementById('viewItemBody');
        modalBody.innerHTML = `
            <div class="item-detail">
                <div class="detail-row">
                    <span class="detail-label">ID:</span>
                    <span class="detail-value">${item.id}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Name:</span>
                    <span class="detail-value">${escapeHtml(item.name)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Description:</span>
                    <span class="detail-value">${escapeHtml(item.description || 'N/A')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Price:</span>
                    <span class="detail-value">$${parseFloat(item.price).toFixed(2)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Category:</span>
                    <span class="detail-value">${escapeHtml(item.category)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Quantity:</span>
                    <span class="detail-value">${item.quantity || 0} in stock</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status:</span>
                    <span class="detail-value">
                        <span class="badge ${item.is_active ? 'active' : 'inactive'}">
                            ${item.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Created:</span>
                    <span class="detail-value">${formatDate(item.created_at)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Updated:</span>
                    <span class="detail-value">${formatDate(item.updated_at)}</span>
                </div>
            </div>
        `;
        
        document.getElementById('viewItemModal').classList.add('active');
    } catch (error) {
        alert('Error loading item details: ' + error.message);
    }
}

function closeViewItemModal() {
    document.getElementById('viewItemModal').classList.remove('active');
}

// Create/Edit Item
function showCreateItemModal() {
    currentEditItemId = null;
    document.getElementById('modalTitle').innerHTML = '<i class="fas fa-plus"></i> Add Item';
    document.getElementById('itemForm').reset();
    document.getElementById('itemId').value = '';
    document.getElementById('itemActive').checked = true;
    document.getElementById('itemModal').classList.add('active');
}

async function editItem(itemId) {
    try {
        const item = await apiCall(`/api/v1/items/${itemId}`);
        
        currentEditItemId = itemId;
        document.getElementById('modalTitle').innerHTML = '<i class="fas fa-edit"></i> Edit Item';
        document.getElementById('itemId').value = item.id;
        document.getElementById('itemName').value = item.name;
        document.getElementById('itemDescription').value = item.description || '';
        document.getElementById('itemPrice').value = item.price;
        document.getElementById('itemCategory').value = item.category;
        document.getElementById('itemActive').checked = item.is_active;
        
        document.getElementById('itemModal').classList.add('active');
    } catch (error) {
        alert('Error loading item: ' + error.message);
    }
}

function closeItemModal() {
    document.getElementById('itemModal').classList.remove('active');
    currentEditItemId = null;
}

async function handleItemSubmit(e) {
    e.preventDefault();
    
    const itemData = {
        name: document.getElementById('itemName').value,
        description: document.getElementById('itemDescription').value || null,
        price: parseFloat(document.getElementById('itemPrice').value),
        category: document.getElementById('itemCategory').value,
        is_active: document.getElementById('itemActive').checked
    };
    
    try {
        if (currentEditItemId) {
            // Update existing item
            await apiCall(`/api/v1/items/${currentEditItemId}`, {
                method: 'PUT',
                body: JSON.stringify(itemData)
            });
            alert('Item updated successfully!');
        } else {
            // Create new item
            await apiCall('/api/v1/items', {
                method: 'POST',
                body: JSON.stringify(itemData)
            });
            alert('Item created successfully!');
        }
        
        closeItemModal();
        loadStats();
        loadCategories();
        loadItems();
    } catch (error) {
        alert('Error saving item: ' + error.message);
    }
}

// Delete Item
async function deleteItem(itemId, itemName) {
    if (!confirm(`Are you sure you want to delete "${itemName}"?`)) {
        return;
    }
    
    try {
        await apiCall(`/api/v1/items/${itemId}`, {
            method: 'DELETE'
        });
        
        alert('Item deleted successfully!');
        loadStats();
        loadCategories();
        loadItems();
    } catch (error) {
        alert('Error deleting item: ' + error.message);
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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

// ==================== Shopping Cart Functions ====================

function saveCart() {
    localStorage.setItem('cart', JSON.stringify(cart));
}

function updateCartBadge() {
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    document.getElementById('cartCount').textContent = totalItems;
}

function addToCart(item) {
    const existingItem = cart.find(cartItem => cartItem.id === item.id);
    
    if (existingItem) {
        existingItem.quantity++;
    } else {
        cart.push({
            id: item.id,
            name: item.name,
            price: item.price,
            category: item.category,
            quantity: 1
        });
    }
    
    saveCart();
    updateCartBadge();
    
    // Show feedback
    const btn = event.target.closest('button');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-check"></i> Added';
    btn.disabled = true;
    
    setTimeout(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }, 1000);
}

function removeFromCart(itemId) {
    cart = cart.filter(item => item.id !== itemId);
    saveCart();
    updateCartBadge();
    renderCart();
}

function updateCartQuantity(itemId, change) {
    const item = cart.find(cartItem => cartItem.id === itemId);
    
    if (item) {
        item.quantity += change;
        
        if (item.quantity <= 0) {
            removeFromCart(itemId);
        } else {
            saveCart();
            renderCart();
            updateCartBadge();
        }
    }
}

function renderCart() {
    const cartItemsDiv = document.getElementById('cartItems');
    
    if (cart.length === 0) {
        cartItemsDiv.innerHTML = '<div class="empty-cart"><i class="fas fa-shopping-cart"></i><p>Your cart is empty</p></div>';
        document.getElementById('cartTotal').textContent = '$0.00';
        return;
    }
    
    let total = 0;
    
    cartItemsDiv.innerHTML = cart.map(item => {
        const itemTotal = item.price * item.quantity;
        total += itemTotal;
        
        return `
            <div class="cart-item">
                <div class="cart-item-info">
                    <h4>${escapeHtml(item.name)}</h4>
                    <p class="cart-item-category"><i class="fas fa-tag"></i> ${escapeHtml(item.category)}</p>
                    <p class="cart-item-price">$${parseFloat(item.price).toFixed(2)} each</p>
                </div>
                <div class="cart-item-controls">
                    <div class="quantity-controls">
                        <button class="btn btn-sm btn-secondary" onclick="updateCartQuantity(${item.id}, -1)">
                            <i class="fas fa-minus"></i>
                        </button>
                        <span class="quantity-display">${item.quantity}</span>
                        <button class="btn btn-sm btn-secondary" onclick="updateCartQuantity(${item.id}, 1)">
                            <i class="fas fa-plus"></i>
                        </button>
                    </div>
                    <div class="cart-item-total">
                        <strong>$${itemTotal.toFixed(2)}</strong>
                    </div>
                    <button class="btn btn-sm btn-danger" onclick="removeFromCart(${item.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    document.getElementById('cartTotal').textContent = `$${total.toFixed(2)}`;
}

function openCartModal() {
    renderCart();
    document.getElementById('cartModal').classList.add('active');
}

function closeCartModal() {
    document.getElementById('cartModal').classList.remove('active');
}

function clearCart() {
    if (confirm('Are you sure you want to clear the cart?')) {
        cart = [];
        saveCart();
        updateCartBadge();
        renderCart();
    }
}

async function placeOrder() {
    if (cart.length === 0) {
        alert('Your cart is empty!');
        return;
    }
    
    if (!confirm(`Place order for ${cart.length} item(s)?`)) {
        return;
    }
    
    try {
        // Prepare order data for backend
        const orderData = {
            items: cart.map(item => ({
                item_id: item.id,
                quantity: item.quantity,
                price: item.price
            })),
            total: cart.reduce((sum, item) => sum + (item.price * item.quantity), 0)
        };
        
        // Send order to backend
        const response = await apiCall('/api/v1/orders', {
            method: 'POST',
            body: JSON.stringify(orderData)
        });
        
        if (response.success) {
            const total = orderData.total;
            alert(`✅ Order placed successfully!\nTotal: $${total.toFixed(2)}\n${response.items_updated} items updated in inventory.\n\nThank you for your order!`);
            
            // Clear cart after successful order
            cart = [];
            saveCart();
            updateCartBadge();
            renderCart();
            closeCartModal();
            
            // Reload items to show updated quantities
            loadItems();
        } else {
            let errorMsg = '❌ Order failed:\n';
            if (response.errors && response.errors.length > 0) {
                errorMsg += response.errors.join('\n');
            }
            alert(errorMsg);
        }
    } catch (error) {
        console.error('Error placing order:', error);
        alert('❌ Failed to place order. Please try again.');
    }
}
