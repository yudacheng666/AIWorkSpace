Option Explicit

Dim fso, shell, root, pythonExe, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
If WScript.Arguments.Count > 0 Then
    If LCase(WScript.Arguments(0)) = "--syntax-check" Then WScript.Quit 0
End If


If Not fso.FileExists(root & "\desktop_launcher.py") Then
    MsgBox "找不到 AIWorkSpace 启动管理程序。", vbCritical, "AI 工作台"
    WScript.Quit 1
End If

pythonExe = FindPython()
If Len(pythonExe) = 0 Then
    MsgBox "找不到 Python。请确认本机 Python 仍正常安装。", vbCritical, "AI 工作台"
    WScript.Quit 1
End If

shell.CurrentDirectory = root
command = Quote(pythonExe) & " " & Quote(root & "\desktop_launcher.py") & " stop"
shell.Run command, 0, False

Function FindPython()
    Dim localApp, programFiles, candidate
    localApp = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
    programFiles = shell.ExpandEnvironmentStrings("%ProgramFiles%")

    candidate = localApp & "\Python\pythoncore-3.15-64\pythonw.exe"
    If fso.FileExists(candidate) Then
        FindPython = candidate
        Exit Function
    End If
    candidate = localApp & "\Programs\Python\Python315\pythonw.exe"
    If fso.FileExists(candidate) Then
        FindPython = candidate
        Exit Function
    End If

    candidate = FindInBase(localApp & "\Python", "pythonw.exe")
    If Len(candidate) = 0 Then candidate = FindInBase(localApp & "\Programs\Python", "pythonw.exe")
    If Len(candidate) = 0 Then candidate = FindPythonInProgramFiles(programFiles, "pythonw.exe")
    If Len(candidate) > 0 Then
        FindPython = candidate
        Exit Function
    End If

    candidate = localApp & "\Python\pythoncore-3.15-64\python.exe"
    If fso.FileExists(candidate) Then
        FindPython = candidate
        Exit Function
    End If
    candidate = localApp & "\Programs\Python\Python315\python.exe"
    If fso.FileExists(candidate) Then
        FindPython = candidate
        Exit Function
    End If
    candidate = FindInBase(localApp & "\Python", "python.exe")
    If Len(candidate) = 0 Then candidate = FindInBase(localApp & "\Programs\Python", "python.exe")
    If Len(candidate) = 0 Then candidate = FindPythonInProgramFiles(programFiles, "python.exe")
    FindPython = candidate
End Function

Function FindInBase(basePath, executableName)
    Dim folder, subfolder, candidate, best
    best = ""
    If Not fso.FolderExists(basePath) Then
        FindInBase = best
        Exit Function
    End If
    Set folder = fso.GetFolder(basePath)
    For Each subfolder In folder.SubFolders
        candidate = subfolder.Path & "\" & executableName
        If fso.FileExists(candidate) Then
            If Len(best) = 0 Or LCase(candidate) > LCase(best) Then best = candidate
        End If
    Next
    FindInBase = best
End Function

Function FindPythonInProgramFiles(basePath, executableName)
    Dim folder, subfolder, candidate, best
    best = ""
    If Not fso.FolderExists(basePath) Then
        FindPythonInProgramFiles = best
        Exit Function
    End If
    Set folder = fso.GetFolder(basePath)
    For Each subfolder In folder.SubFolders
        If LCase(Left(subfolder.Name, 6)) = "python" Then
            candidate = subfolder.Path & "\" & executableName
            If fso.FileExists(candidate) Then
                If Len(best) = 0 Or LCase(candidate) > LCase(best) Then best = candidate
            End If
        End If
    Next
    FindPythonInProgramFiles = best
End Function

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function
