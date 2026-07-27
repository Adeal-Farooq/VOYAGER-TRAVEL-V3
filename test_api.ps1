$url = "http://localhost:8000/api/routes/all-segments?source=Yelahanka+Old+Town&dest=Mahatma+Gandhi+Road&group_size=1&budget=200"
try {
    $result = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 90
    Write-Host "Status: $($result.status)"
    $segs = $result.data.segments
    Write-Host "Segments: $($segs.Count)"
    foreach ($s in $segs) {
        Write-Host "  Seg $($s.segment_index): type=$($s.type), $($s.direct_options.Count) direct, $($s.destinations.Count) dests"
    }
} catch {
    Write-Host "Error: $_"
}
