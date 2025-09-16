fsutil file createnew C:\srd_dummy.bin 5000000000
Start-Sleep -Seconds 600
Remove-Item C:\srd_dummy.bin -Force