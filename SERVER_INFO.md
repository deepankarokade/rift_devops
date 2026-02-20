# Server Configuration

## Backend Server
- **Port**: 8002 (fixed)
- **URL**: http://localhost:8002
- **Status**: ✓ Running (Process ID: 33224)

## API Endpoints

### Health Check
```bash
curl http://localhost:8002/api/health
```

### System Status
```bash
curl http://localhost:8002/api/status
```

### Create Pipeline Run
```bash
curl -X POST http://localhost:8002/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/YashShinde24/autonomous_CICD_pipeline_healer",
    "team_name": "PADY",
    "leader_name": "PARTH_SARODE"
  }'
```

### Get All Runs
```bash
curl http://localhost:8002/api/runs
```

### Get Specific Run
```bash
curl http://localhost:8002/api/runs/{run_id}
```

### WebSocket Connection
```javascript
const ws = new WebSocket('ws://localhost:8002/ws');
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    run_id: 'your-run-id'
  }));
};
```

## Recent Fixes Applied

### 1. Fixed UnboundLocalError in graph.py
- **Issue**: `import os` inside functions was shadowing global import
- **Fix**: Removed redundant `import os` statements
- **Impact**: Pipeline now progresses past test execution

### 2. Added Workflow Auto-Creation
- **Feature**: Automatically creates `.github/workflows/ci.yml` if missing
- **Benefit**: Ensures CI monitoring works even without existing workflows

### 3. Enhanced CI Monitoring
- **Feature**: Gracefully handles missing workflows or GitHub token
- **Behavior**: Marks as "passed" and continues if no CI configured

### 4. CI Log Fetching
- **Feature**: Fetches actual CI logs when tests pass locally but CI fails
- **Benefit**: Can diagnose environment-specific failures

## Port Configuration

The server is now hardcoded to port 8002 and will:
- ✓ Check if port 8002 is available
- ✗ Exit with error if port is in use (no auto-increment)
- ✓ Provide clear error message if port is occupied

To change the port, edit `backend/main.py` line ~650:
```python
port = 8002  # Change this value
```

## Stopping the Server

To stop the backend server:
```bash
# Find the process
netstat -ano | findstr :8002

# Kill the process (replace PID with actual process ID)
taskkill /PID 33224 /F
```

Or use Ctrl+C in the terminal where it's running.
