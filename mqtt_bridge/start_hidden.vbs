Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)
strPythonw = strDir & "\.venv\Scripts\pythonw.exe"
strScript = strDir & "\rival3_mqtt_bridge.py"
objShell.Run """" & strPythonw & """ """ & strScript & """", 0, False
