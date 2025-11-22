# 🎨 Frontend Applications Guide

## 📋 Overview

The project now has two separate frontend applications for different user roles:

1. **User Frontend** - Default landing page at `/` for item management
2. **Admin Frontend** - Management dashboard at `/admin/` for system administration

## 🚀 Quick Start

### Start with Docker (Recommended)

```bash
cd /path/to/project
docker compose -f docker/docker-compose.yaml up -d
```

### Access the Applications

- **User Frontend**: http://localhost:8080/
- **Admin Frontend**: http://localhost:8080/admin/

---

## 👤 User Frontend (`/`)

### Purpose
Simple items management interface for regular authenticated users.

### Features
- ✅ **Item Management**: Create, view, edit, and delete items
- ✅ **Dashboard Statistics**: Total items, active items, categories count
- ✅ **Search & Filter**: Search by name, filter by category and active status
- ✅ **Modern UI**: Card-based layout with responsive grid
- ✅ **Secure Authentication**: JWT token-based login

### Default Credentials
```
Username: testuser
Password: User123!
```

### File Structure
```
frontend/
├── index.html          # User frontend HTML
├── user-app.js         # User frontend JavaScript
└── user-styles.css     # User frontend CSS
```

### API Endpoints Used
- `POST /api/v1/auth/login` - User authentication
- `GET /api/v1/auth/me` - Get current user info
- `GET /api/v1/stats` - Dashboard statistics
- `GET /api/v1/categories` - Available categories
- `GET /api/v1/items` - List items (with filters)
- `POST /api/v1/items` - Create new item
- `PUT /api/v1/items/{id}` - Update item
- `DELETE /api/v1/items/{id}` - Delete item

### User Interface Sections

#### Login Screen
- Username and password fields
- "Remember me" option
- Link to admin dashboard
- Error message display

#### Dashboard
- **Stats Cards**: Total items, active items, categories
- **Toolbar**: Search box, category filter, active-only checkbox, create button
- **Items Grid**: Responsive card layout showing all items

#### Item Card
- Item name (header)
- Status badge (active/inactive)
- Description
- Price
- Category
- Created date
- Actions: View, Edit, Delete

#### Modals
- **Create/Edit Item**: Form with name, description, price, category, active checkbox
- **View Details**: Read-only item information display

---

## 🔧 Admin Frontend (`/admin/`)

### Purpose
Comprehensive management dashboard for administrators with full system control.

### Features
- ✅ **Dashboard Overview**: Real-time system statistics
- ✅ **User Management**: Create, edit, activate/deactivate users
- ✅ **Session Management**: Monitor and revoke active sessions
- ✅ **Security Monitoring**: Track suspicious logins and alerts
- ✅ **Activity Logs**: Recent logins and session revocations
- ✅ **Role-Based Access**: Admin-only access with RBAC

### Admin Credentials
```
Username: admin
Password: Admin123!
```

### File Structure
```
frontend/admin/
├── index.html          # Admin frontend HTML
├── app.js             # Admin frontend JavaScript
└── styles.css         # Admin frontend CSS
```

### API Endpoints Used
- `POST /api/v1/auth/login` - Admin authentication
- `GET /api/v1/admin/dashboard` - Overview statistics
- `GET /api/v1/admin/users` - List all users
- `POST /api/v1/admin/users` - Create new user
- `PUT /api/v1/admin/users/{id}` - Update user
- `PATCH /api/v1/admin/users/{id}/activate` - Activate user
- `PATCH /api/v1/admin/users/{id}/deactivate` - Deactivate user
- `GET /api/v1/admin/sessions` - List all sessions
- `DELETE /api/v1/admin/sessions/{id}` - Revoke session
- `GET /api/v1/admin/security/suspicious-logins` - Security alerts
- `GET /api/v1/admin/activity` - Activity logs

### Admin Interface Sections

#### Dashboard Overview
- Total users count
- Active sessions count
- Suspicious logins count
- Charts and visualizations

#### User Management
- User listing with search and filters
- Create new user form
- Edit user details
- Activate/deactivate users
- Role assignment (admin/user)

#### Session Management
- Active sessions list
- Session details (user, IP, device)
- Revoke session capability
- Session duration tracking

#### Security Monitoring
- Suspicious login attempts
- Failed authentication logs
- IP-based alerts
- Security event timeline

#### Activity Logs
- Recent login history
- Session revocation logs
- User activity tracking
- Timestamp and details

---

## 🐳 Docker Configuration

### NGINX Routing

The frontend service uses NGINX with dual routing:

```nginx
# User frontend (default)
location / {
    try_files $uri $uri/ /index.html;
}

# Admin frontend
location /admin {
    alias /usr/share/nginx/html/admin;
    try_files $uri $uri/ /admin/index.html;
}
```

### Container Details
- **Image**: nginx:alpine
- **Port**: 8080:80
- **Health Check**: GET /health every 30s
- **Restart Policy**: unless-stopped

### Rebuild Frontend

After making changes to frontend files:

```bash
# Rebuild and restart
docker compose -f docker/docker-compose.yaml build frontend
docker compose -f docker/docker-compose.yaml up -d frontend

# Check status
docker ps | grep frontend
```

---

## 🔒 Security

### Authentication
Both frontends use JWT token-based authentication:
- Tokens stored in localStorage
- Auto-logout on 401 responses
- Token included in all API requests

### Authorization
- User Frontend: Any authenticated user
- Admin Frontend: Admin role required (RBAC enforced by backend)

### CORS Configuration
Backend `.env` should include:

```bash
CORS_ORIGINS=http://localhost:8080
```

---

## 🎨 Styling

Both frontends share a consistent design system:

### Colors
- Primary: `#2563eb` (blue)
- Secondary: `#64748b` (slate)
- Success: `#10b981` (green)
- Danger: `#ef4444` (red)
- Warning: `#f59e0b` (amber)
- Info: `#3b82f6` (blue)

### Typography
- Font: System fonts (San Francisco, Segoe UI, etc.)
- Line height: 1.6
- Responsive sizing

### Components
- Cards with shadow and hover effects
- Modals with overlay
- Buttons with multiple variants
- Form controls with focus states
- Badges for status indicators
- Responsive grid layouts

---

## 📱 Responsive Design

### Breakpoints
- Mobile: < 768px
- Tablet: 768px - 1024px
- Desktop: > 1024px

### Mobile Optimizations
- Single column layouts
- Stacked toolbars
- Touch-friendly buttons
- Simplified navigation

---

## 🧪 Testing

### Manual Testing Checklist

#### User Frontend
- [ ] Login with test user credentials
- [ ] View items grid
- [ ] Search items by name
- [ ] Filter by category
- [ ] Filter active items only
- [ ] Create new item
- [ ] Edit existing item
- [ ] Delete item (with confirmation)
- [ ] View item details
- [ ] Verify stats cards update
- [ ] Test responsive layout
- [ ] Navigate to admin (should redirect if not admin)

#### Admin Frontend
- [ ] Login with admin credentials
- [ ] View dashboard statistics
- [ ] List all users
- [ ] Search and filter users
- [ ] Create new user
- [ ] Edit user details
- [ ] Activate/deactivate user
- [ ] View active sessions
- [ ] Revoke session
- [ ] View suspicious logins
- [ ] View activity logs
- [ ] Test all modal forms
- [ ] Verify role-based access

---

## 🐛 Troubleshooting

### Frontend Not Loading
```bash
# Check container status
docker ps | grep frontend

# View logs
docker logs docker-frontend-1

# Restart container
docker compose -f docker/docker-compose.yaml restart frontend
```

### API Connection Issues
1. Verify backend is running on port 8000
2. Check CORS settings in backend `.env`
3. Verify network connectivity: `docker network inspect docker_app-network`

### Authentication Errors
1. Clear browser localStorage
2. Verify credentials match database users
3. Check backend logs for authentication failures

### NGINX Routing Issues
1. Verify nginx-frontend.conf syntax
2. Check NGINX logs: `docker exec docker-frontend-1 cat /var/log/nginx/error.log`
3. Test health endpoint: `curl http://localhost:8080/health`

---

## 📊 Port Allocation

- **8000**: Backend API
- **8080**: Frontend (both user and admin)
- **5432**: PostgreSQL
- **6379**: Redis
- **3000**: Grafana
- **9090**: Prometheus

---

## 🔄 Development Workflow

### Local Development (Without Docker)

```bash
# Start frontend server
cd frontend
./start.sh

# Or use Python directly
python3 -m http.server 8080
```

### Making Changes

1. Edit files in `frontend/` directory
2. For admin: Edit files in `frontend/admin/`
3. Rebuild Docker: `docker compose -f docker/docker-compose.yaml build frontend`
4. Restart: `docker compose -f docker/docker-compose.yaml up -d frontend`
5. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)

---

## 📚 Additional Resources

- **Backend API Documentation**: See `app/README.md`
- **Docker Setup**: See `docker/README.md`
- **Full Project Guide**: See main `README.md`

---

## ✅ Summary

You now have two fully functional frontends:

1. **User Frontend** (`/`) - Items management for all users
   - Login: testuser / User123!
   - Features: CRUD operations on items, search, filter

2. **Admin Frontend** (`/admin/`) - System administration for admins
   - Login: admin / Admin123!
   - Features: User management, sessions, security monitoring

Both accessible via http://localhost:8080 with role-based routing and authentication.
