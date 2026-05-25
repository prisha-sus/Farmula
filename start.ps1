# Farmula startup script
# Run from project root: .\start.ps1

Write-Host "Stopping any existing Farmula processes..." -ForegroundColor Yellow

# Kill anything on our ports
$ports = @(8006, 5173, 5174, 5175)
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 3
Write-Host "Ports cleared." -ForegroundColor Green

# Start FastAPI backend
Write-Host "Starting FastAPI backend on port 8006..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; uvicorn api.main:app --port 8006 --reload"

Start-Sleep -Seconds 3

# Start React frontend
Write-Host "Starting React frontend on port 5173..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; npm run dev -- --port 5173"

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Farmula is starting up..." -ForegroundColor Green
Write-Host "Backend:  http://127.0.0.1:8006" -ForegroundColor White
Write-Host "Frontend: http://127.0.0.1:5173" -ForegroundColor White
Write-Host ""
Write-Host "Opening browser in 5 seconds..."
Start-Sleep -Seconds 5
Start-Process "http://127.0.0.1:5173"
