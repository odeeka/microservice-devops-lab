# 🎨 Admin Dashboard Frontend

A modern, responsive web interface for the Microservice DevOps Lab Admin Dashboard.

## 🌟 Features

- **📊 Dashboard Overview** - Real-time system statistics and metrics
- **👥 User Management** - View, search, filter, activate/deactivate users
- **📱 Session Management** - Monitor and revoke user sessions
- **🔒 Security Monitoring** - Track suspicious logins and security alerts
- **📅 Activity Logs** - Recent logins and session revocations
- **🎨 Modern UI** - Clean, responsive design with smooth animations
- **🔐 Secure** - JWT token-based authentication with role checking

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Start all services including frontend
cd /path/to/project
make up
# or
docker compose -f docker/docker-compose.yaml up -d
```

Then open http://localhost:8080 in your browser.

### Option 2: Python HTTP Server

```bash
cd frontend
chmod +x start.sh
./start.sh
```

Then open http://localhost:8080 in your browser.

### Option 3: Node.js HTTP Server

```bash
cd frontend
npx http-server -p 8080
```

### Option 4: PHP Built-in Server

```bash
cd frontend
php -S localhost:8080
```

### Option 5: Any Static File Server

Simply serve the `frontend` directory on port 8080 or any port you prefer.

⚠️ **Note**: Port 3000 is used by Grafana, so the frontend runs on port 8080.

## 📋 Prerequisites

1. **Backend API must be running** at http://localhost:8000
   ```bash
   cd /path/to/project
   make up
   # or
   docker compose -f docker/docker-compose.yaml up -d
   ```

2. **Admin account** for login:
   - Username: `admin`
   - Password: `Admin123!`

## 🎯 Usage

### 1. Login

1. Open http://localhost:3000
2. Enter credentials:
   - **Username**: `admin`
   - **Password**: `Admin123!`
   - **API URL**: `http://localhost:8000` (default)
3. Click "Login"

### 2. Navigate the Dashboard

- **Overview** - View system statistics (users, sessions, security metrics)
- **Users** - Manage user accounts (search, filter, activate/deactivate)
- **Sessions** - Monitor active sessions and revoke suspicious ones
- **Security** - Check suspicious logins with risk scores
- **Activity** - View recent login and revocation history

### 3. Key Actions

**User Management:**
- 🔍 Search users by username or email
- 🎯 Filter by role (admin/user/readonly)
- ✅ Activate/deactivate user accounts
- 👁️ View detailed user information

**Session Management:**
- 📱 View all active sessions
- 🚫 Revoke suspicious or compromised sessions
- 📊 Monitor risk scores and device information

**Security Monitoring:**
- 🚨 Track suspicious logins
- 📈 Adjust risk score thresholds
- 🔍 View risk factors and recommendations

## 🛠️ Configuration

### Change API URL

You can change the API URL on the login screen or edit `app.js`:

```javascript
let apiUrl = 'http://your-api-server:8000';
```

### Docker Ports

- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8000
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090

### CORS Configuration

Make sure your backend API allows requests from the frontend origin. Update your FastAPI CORS settings in `app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",  # Frontend (Docker)
        "http://localhost:3000",  # Alternative frontend port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📁 File Structure

```
frontend/
├── index.html          # Main HTML structure
├── styles.css          # Styling and responsive design
├── app.js              # JavaScript logic and API calls
├── start.sh            # Quick start script
└── README.md           # This file
```

## 🎨 Features Detail

### Dashboard Overview
- Total users count
- Active users count
- Active sessions count
- Suspicious logins (last 7 days)
- User distribution by role
- Recent activity statistics

### User Management
- **Search**: Real-time search by username or email
- **Filter**: By role (admin/user/readonly) and active status
- **Actions**: View details, activate, deactivate
- **Pagination**: Load up to 100 users

### Session Management
- **View**: All sessions or active only
- **Details**: Session ID, user, device, IP, timestamps, risk score
- **Actions**: Revoke individual sessions
- **Monitoring**: Track session activity and expiration

### Security Monitoring
- **Suspicious Logins**: Filter by days and minimum risk score
- **Risk Analysis**: View risk factors and recommendations
- **Time Range**: Configurable lookback period (1-30 days)
- **Risk Threshold**: Adjustable minimum risk score (0-100)

### Activity Logs
- **Recent Logins**: Last 24 hours (configurable)
- **Revocations**: Session termination history
- **Details**: User, device, IP, timestamp, reason

## 🔒 Security Features

✅ **JWT Authentication** - Secure token-based auth  
✅ **Token Storage** - Saved in localStorage for persistence  
✅ **Auto Logout** - On 401 unauthorized responses  
✅ **Role Check** - Ensures only admins can access  
✅ **HTTPS Ready** - Works with HTTPS backends  

## 🐛 Troubleshooting

### Cannot connect to API

**Error**: "Invalid credentials or API not reachable"

**Solution**:
1. Check if backend is running: `curl http://localhost:8000/health`
2. Verify API URL on login screen
3. Check CORS settings in backend

### Login fails with valid credentials

**Error**: "Access denied. Admin role required."

**Solution**:
- Ensure you're logging in with an admin account
- Default admin credentials:
  - Username: `admin`
  - Password: `Admin123!`

### Empty data tables

**Possible causes**:
1. No data in database (run seed script)
2. API endpoint error (check browser console)
3. Token expired (logout and login again)

### CORS errors in browser console

**Error**: "Access to fetch at 'http://localhost:8000/...' from origin 'http://localhost:3000' has been blocked by CORS policy"

**Solution**: Update backend CORS settings to allow frontend origin:

```python
# In app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📱 Responsive Design

The dashboard is fully responsive and works on:
- 🖥️ Desktop (1920px+)
- 💻 Laptop (1024px - 1920px)
- 📱 Tablet (768px - 1024px)
- 📱 Mobile (< 768px)

## 🎯 Browser Support

✅ Chrome 90+  
✅ Firefox 88+  
✅ Safari 14+  
✅ Edge 90+  

## 🚀 Production Deployment

### Using NGINX

```nginx
server {
    listen 80;
    server_name admin.yourdomain.com;
    
    root /path/to/frontend;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # API proxy (optional)
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Using Docker

Create `Dockerfile`:

```dockerfile
FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
```

Build and run:
```bash
docker build -t admin-dashboard .
docker run -d -p 3000:80 admin-dashboard
```

## 📚 API Endpoints Used

The frontend connects to these backend endpoints:

- `POST /api/v1/auth/login` - User authentication
- `GET /api/v1/auth/me` - Get current user info
- `GET /api/v1/admin/dashboard/overview` - System statistics
- `GET /api/v1/admin/dashboard/activity` - Recent activity
- `GET /api/v1/admin/users` - List users
- `GET /api/v1/admin/users/{id}` - User details
- `POST /api/v1/admin/users/{id}/activate` - Activate user
- `POST /api/v1/admin/users/{id}/deactivate` - Deactivate user
- `GET /api/v1/admin/sessions/all` - List sessions
- `DELETE /api/v1/admin/sessions/{id}` - Revoke session
- `GET /api/v1/admin/security/suspicious-logins` - Suspicious logins

## 🤝 Contributing

Improvements welcome! Areas to enhance:
- Advanced filtering and sorting
- Export data to CSV/PDF
- Charts and graphs (Chart.js integration)
- Real-time updates (WebSocket support)
- Dark mode toggle
- Multi-language support

## 📄 License

Same as the main project.

## 🎉 Enjoy!

You now have a fully functional admin dashboard! 🚀

For backend documentation, see: [../docs/ADMIN_DASHBOARD.md](../docs/ADMIN_DASHBOARD.md)
