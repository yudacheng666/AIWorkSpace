Option Explicit

Dim fso, shell, root, appData, configDir, configPath, dataDir, rootAbs, dataAbs
Dim stream, desktop, shortcut, target

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)

If WScript.Arguments.Count > 0 Then
    If LCase(WScript.Arguments(0)) = "--syntax-check" Then WScript.Quit 0
End If

If Not fso.FileExists(root & "\app.py") Or _
   Not fso.FileExists(root & "\start_aiworkspace.vbs") Or _
   Not fso.FileExists(root & "\stop_aiworkspace.vbs") Then
    MsgBox U("8BF7,5C06,6B64,811A,672C,653E,5728,5B8C,6574,7684,0020,0041,0049,0057,006F,0072,006B,0053,0070,0061,0063,0065,0020,7A0B,5E8F,6587,4EF6,5939,4E2D,8FD0,884C,3002"), vbCritical, U("0041,0049,0020,5DE5,4F5C,53F0,9996,6B21,8BBE,7F6E")
    WScript.Quit 1
End If

dataDir = InputBox( _
    U("8BF7,8F93,5165,73B0,6709,7684,0020,0047,006F,006F,0067,006C,0065,0020,0044,0072,0069,0076,0065,0020,5DE5,4F5C,53F0,6570,636E,76EE,5F55,3002") & vbCrLf & vbCrLf & _
    U("8BF7,9009,62E9,6570,636E,6839,76EE,5F55,FF0C,4E0D,8981,9009,62E9,0020,0065,0076,0065,006E,0074,0073,0020,5B50,6587,4EF6,5939,3002") & vbCrLf & _
    "Example: X:\My Drive\AIWorkSpaceData", _
    U("0041,0049,0020,5DE5,4F5C,53F0,9996,6B21,8BBE,7F6E"))

dataDir = Trim(dataDir)
If Len(dataDir) = 0 Then WScript.Quit 0
If Not fso.FolderExists(dataDir) Then
    MsgBox U("627E,4E0D,5230,8FD9,4E2A,6587,4EF6,5939,3002,8BF7,786E,8BA4,0020,0047,006F,006F,0067,006C,0065,0020,0044,0072,0069,0076,0065,0020,5DF2,542F,52A8,FF0C,5E76,8F93,5165,73B0,6709,6570,636E,76EE,5F55,3002"), vbExclamation, U("0041,0049,0020,5DE5,4F5C,53F0,9996,6B21,8BBE,7F6E")
    WScript.Quit 1
End If
If Not fso.FolderExists(dataDir & "\events") Then
    MsgBox U("6240,9009,76EE,5F55,4E2D,6CA1,6709,0020,0065,0076,0065,006E,0074,0073,0020,5B50,6587,4EF6,5939,3002,8BF7,786E,8BA4,9009,62E9,7684,662F,73B0,6709,0020,0041,0049,0057,006F,0072,006B,0053,0070,0061,0063,0065,0044,0061,0074,0061,0020,6570,636E,6839,76EE,5F55,3002"), vbCritical, U("0041,0049,0020,5DE5,4F5C,53F0,9996,6B21,8BBE,7F6E")
    WScript.Quit 1
End If
If LCase(fso.GetFileName(fso.GetAbsolutePathName(dataDir))) = "events" Or _
   LCase(fso.GetFileName(fso.GetAbsolutePathName(dataDir))) = "project_events" Or _
   LCase(fso.GetFileName(fso.GetAbsolutePathName(dataDir))) = "step_events" Then
    MsgBox U("8BF7,9009,62E9,0020,0041,0049,0057,006F,0072,006B,0053,0070,0061,0063,0065,0044,0061,0074,0061,0020,6570,636E,6839,76EE,5F55,FF0C,4E0D,8981,9009,62E9,0020,0065,0076,0065,006E,0074,0073,3001,0070,0072,006F,006A,0065,0063,0074,005F,0065,0076,0065,006E,0074,0073,0020,6216,0020,0073,0074,0065,0070,005F,0065,0076,0065,006E,0074,0073,0020,5B50,6587,4EF6,5939,3002"), vbCritical, U("0041,0049,0020,5DE5,4F5C,53F0,9996,6B21,8BBE,7F6E")
    WScript.Quit 1
End If

rootAbs = LCase(fso.GetAbsolutePathName(root))
dataAbs = LCase(fso.GetAbsolutePathName(dataDir))
If dataAbs = rootAbs Or Left(dataAbs, Len(rootAbs) + 1) = rootAbs & "\" Or _
   Left(rootAbs, Len(dataAbs) + 1) = dataAbs & "\" Then
    MsgBox U("6570,636E,76EE,5F55,4E0D,80FD,4E0E,7A0B,5E8F,76EE,5F55,76F8,540C,3001,4E92,76F8,5305,542B,6216,4F4D,4E8E,7A0B,5E8F,76EE,5F55,5185,3002,6CA1,6709,4FDD,5B58,4EFB,4F55,8BBE,7F6E,3002"), vbCritical, U("0041,0049,0020,5DE5,4F5C,53F0,9996,6B21,8BBE,7F6E")
    WScript.Quit 1
End If

appData = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
configDir = appData & "\AIWorkSpace"
configPath = configDir & "\launcher.json"
If Not fso.FolderExists(configDir) Then fso.CreateFolder(configDir)

Set stream = CreateObject("ADODB.Stream")
stream.Type = 2
stream.Charset = "utf-8"
stream.Open
stream.WriteText "{""data_dir"":""" & JsonEscape(fso.GetAbsolutePathName(dataDir)) & """,""port"":8770}" & vbCrLf
stream.SaveToFile configPath, 2
stream.Close

desktop = shell.SpecialFolders("Desktop")
target = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wscript.exe"

Set shortcut = shell.CreateShortcut(desktop & "\" & U("0041,0049,0020,5DE5,4F5C,53F0") & ".lnk")
shortcut.TargetPath = target
shortcut.Arguments = Chr(34) & root & "\start_aiworkspace.vbs" & Chr(34)
shortcut.WorkingDirectory = root
shortcut.Description = U("540E,53F0,542F,52A8,0020,0041,0049,0057,006F,0072,006B,0053,0070,0061,0063,0065,0020,5E76,6253,5F00,5DE5,4F5C,53F0,7F51,9875")
shortcut.Save

Set shortcut = shell.CreateShortcut(desktop & "\" & U("5173,95ED,0020,0041,0049,0020,5DE5,4F5C,53F0") & ".lnk")
shortcut.TargetPath = target
shortcut.Arguments = Chr(34) & root & "\stop_aiworkspace.vbs" & Chr(34)
shortcut.WorkingDirectory = root
shortcut.Description = U("5B89,5168,505C,6B62,7531,684C,9762,5FEB,6377,65B9,5F0F,542F,52A8,7684,0020,0041,0049,0057,006F,0072,006B,0053,0070,0061,0063,0065,0020,670D,52A1")
shortcut.Save

MsgBox U("8BBE,7F6E,5B8C,6210,FF0C,5DF2,5728,684C,9762,521B,5EFA,4E24,4E2A,5FEB,6377,65B9,5F0F,FF1A") & vbCrLf & _
       "1. " & U("0041,0049,0020,5DE5,4F5C,53F0") & vbCrLf & _
       "2. " & U("5173,95ED,0020,0041,0049,0020,5DE5,4F5C,53F0") & vbCrLf & vbCrLf & _
       U("6570,636E,76EE,5F55,FF1A") & fso.GetAbsolutePathName(dataDir) & vbCrLf & _
       U("672C,673A,8BBE,7F6E,4FDD,5B58,5728,0020,004C,006F,0063,0061,006C,0041,0070,0070,0044,0061,0074,0061,FF0C,4E0D,4F1A,540C,6B65,5230,0020,0047,006F,006F,0067,006C,0065,0020,0044,0072,0069,0076,0065,0020,6216,63D0,4EA4,5230,0020,0047,0069,0074,0048,0075,0062,3002"), _
       vbInformation, U("0041,0049,0020,5DE5,4F5C,53F0,9996,6B21,8BBE,7F6E")

Function JsonEscape(value)
    value = Replace(value, "\", "\\")
    value = Replace(value, Chr(34), "\" & Chr(34))
    value = Replace(value, vbCr, "\r")
    value = Replace(value, vbLf, "\n")
    JsonEscape = value
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
