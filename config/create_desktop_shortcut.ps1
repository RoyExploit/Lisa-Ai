$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('C:\Users\ravit\OneDrive\Desktop\Lisa AI.lnk')
$Shortcut.TargetPath = 'D:\TiTech Prabha Solution\Lisa AI\Lisa AI\Lisa-AI---Lite-main\Lisa-AI---Lite-main\.venv\Scripts\pythonw.exe'
$Shortcut.Arguments = '"D:\TiTech Prabha Solution\Lisa AI\Lisa AI\Lisa-AI---Lite-main\Lisa-AI---Lite-main\main.py"'
$Shortcut.WorkingDirectory = 'D:\TiTech Prabha Solution\Lisa AI\Lisa AI\Lisa-AI---Lite-main\Lisa-AI---Lite-main'
$Shortcut.WindowStyle = 7
$Shortcut.Description = 'Launch Lisa AI'
if ('D:\TiTech Prabha Solution\Lisa AI\Lisa AI\Lisa-AI---Lite-main\Lisa-AI---Lite-main\assets\Lisa_Lite_Logo.ico') { $Shortcut.IconLocation = 'D:\TiTech Prabha Solution\Lisa AI\Lisa AI\Lisa-AI---Lite-main\Lisa-AI---Lite-main\assets\Lisa_Lite_Logo.ico,0' }
$Shortcut.Save()