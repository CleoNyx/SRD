$mem = @()
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalMinutes -lt 6) { $mem += ,(New-Object byte[] (50MB)); Start-Sleep -Milliseconds 200 }