# OSRM Setup Script for VOYAGER
# Downloads Karnataka OSM data and sets up local OSRM routing

Write-Host "=== VOYAGER OSRM Setup ===" -ForegroundColor Cyan
Write-Host "This script will download Karnataka OSM data and set up OSRM containers."
Write-Host "Note: Initial setup requires ~300MB download and ~30min processing time."
Write-Host ""

$OSRM_DIR = Join-Path $PSScriptRoot "..\osrm-data"
if (!(Test-Path $OSRM_DIR)) { New-Item -ItemType Directory -Path $OSRM_DIR -Force }

# Download Karnataka OSM PBF (~100MB)
$PBF_URL = "https://download.geofabrik.de/asia/india/karnataka-latest.osm.pbf"
$PBF_PATH = Join-Path $OSRM_DIR "karnataka.osm.pbf"

if (!(Test-Path $PBF_PATH)) {
    Write-Host "Downloading Karnataka OSM data (~100MB)..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $PBF_URL -OutFile $PBF_PATH -UseBasicParsing
    Write-Host "Download complete!" -ForegroundColor Green
} else {
    Write-Host "Karnataka OSM data already downloaded." -ForegroundColor Green
}

# Build OSRM containers
Write-Host ""
Write-Host "Starting OSRM containers..." -ForegroundColor Yellow

# Create a Dockerfile for the OSRM setup
@"
FROM ghcr.io/project-osrm/osrm-backend:latest
COPY karnataka.osm.pbf /data/karnataka.osm.pbf
RUN osrm-extract -p /opt/car.lua /data/karnataka.osm.pbf && \
    osrm-partition /data/karnataka.osrm && \
    osrm-customize /data/karnataka.osrm
CMD osrm-routed --algorithm mld /data/karnataka.osrm --port 5000
"@ | Set-Content (Join-Path $OSRM_DIR "Dockerfile.osrm")

# Build the OSRM image (this takes 20-30 minutes)
Write-Host "Building OSRM image (this takes 20-30 minutes)..." -ForegroundColor Yellow
Set-Location -LiteralPath $OSRM_DIR
docker build -t voyager-osrm -f Dockerfile.osrm .
Set-Location -LiteralPath (Join-Path $PSScriptRoot "..")

Write-Host ""
Write-Host "=== OSRM Setup Complete ===" -ForegroundColor Green
Write-Host "Run 'docker compose up -d osrm-car osrm-foot' to start OSRM services."
Write-Host "The API will be available at http://localhost:5000" -ForegroundColor Cyan
