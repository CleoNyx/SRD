$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalMinutes -lt 6) { 1..100000 | % { [Math]::Sqrt($_) } > $null }