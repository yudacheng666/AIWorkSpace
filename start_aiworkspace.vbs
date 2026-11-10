Option Explicit

Dim fso, shell, root, configPath, pythonExe, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)

If WScript.Arguments.Count > 0 Then
    If LCase(WScript.Arguments(0)) = "--syntax-check" Then WScript.Quit 0
End If

configPath = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\AIWorkSpace\launcher.json"
If Not fso.FileExists(root & "\app.py") Or Not fso.FileExists(root & "\desktop_launcher.py") Then
    MsgBox U("627E,4E0D,5230,0020,0041,0049,0057,006F,0072,006B,0053,0070,0061,0063,0065,0020,7A0B,5E8F,6587,4EF6,3002,8BF7,4ECE,7A0B,5E8F,6587,4EF6,5939,4E2D,7684,684C,9762,542F,52A8,811A,672C,8FD0,884C,3002"), vbCritical, U("0041,0049,0020,5DE5,4F5C,53F0")
    WScript.Quit 1
End If

If Not fso.FileExists(configPath) Then
    MsgBox U("5C1A,672A,5B8C,6210,9996,6B21,8BBE,7F6E,3002,8BF7,5148,53CC,51FB,0020,0073,0065,0074,0075,0070,005F,0064,0065,0073,006B,0074,006F,0070,005F,0073,0068,006F,0072,0074,0063,0075,0074,0073,002E,0076,0062,0073,3002"), vbInformation, U("0041,0049,0020,5DE5,4F5C,53F0")
    WScript.Quit 1
End If

pythonExe = FindPython()
If Len(pythonExe) = 0 Then
    MsgBox U("627E,4E0D,5230,0020,0050,0079,0074,0068,006F,006E,3002,8BF7,786E,8BA4,5DF2,5B89,88C5,0020,0050,0079,0074,0068,006F,006E,0020,0033,FF0C,6216,68C0,67E5,672C,673A,0020,0050,0079,0074,0068,006F,006E,0020,5B89,88C5,76EE,5F55,3002"), vbCritical, U("0041,0049,0020,5DE5,4F5C,53F0")
    WScript.Quit 1
End If

shell.CurrentDirectory = root
command = Quote(pythonExe) & " " & Quote(root & "\desktop_launcher.py") & " start"
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

Function U(hexCodes)
    Dim parts, i, result
    parts = Split(hexCodes, ",")
    result = ""
    For i = 0 To UBound(parts)
        result = result & ChrW(CLng("&H" & parts(i)))
    Next
    U = result
End Function
