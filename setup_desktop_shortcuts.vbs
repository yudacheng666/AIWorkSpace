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
    MsgBox "请将此脚本放在完整的 AIWorkSpace 程序文件夹中运行。", vbCritical, "AI 工作台首次设置"
    WScript.Quit 1
End If

dataDir = InputBox( _
    "请输入现有的 Google Drive 工作台数据目录。" & vbCrLf & vbCrLf & _
    "请选择数据根目录，不要选择 events 子文件夹。" & vbCrLf & _
    "例如：X:\My Drive\AIWorkSpaceData", _
    "AI 工作台首次设置")

dataDir = Trim(dataDir)
If Len(dataDir) = 0 Then WScript.Quit 0
If Not fso.FolderExists(dataDir) Then
    MsgBox "找不到这个文件夹。请确认 Google Drive 已启动，并输入现有数据目录。", vbExclamation, "AI 工作台首次设置"
    WScript.Quit 1
End If
If Not fso.FolderExists(dataDir & "\events") Then
    MsgBox "所选目录中没有 events 子文件夹。请确认选择的是现有 AIWorkSpaceData 数据根目录。", vbCritical, "AI 工作台首次设置"
    WScript.Quit 1
End If
If LCase(fso.GetFileName(fso.GetAbsolutePathName(dataDir))) = "events" Or _
   LCase(fso.GetFileName(fso.GetAbsolutePathName(dataDir))) = "project_events" Or _
   LCase(fso.GetFileName(fso.GetAbsolutePathName(dataDir))) = "step_events" Then
    MsgBox "请选择 AIWorkSpaceData 数据根目录，不要选择 events、project_events 或 step_events 子文件夹。", vbCritical, "AI 工作台首次设置"
    WScript.Quit 1
End If

rootAbs = LCase(fso.GetAbsolutePathName(root))
dataAbs = LCase(fso.GetAbsolutePathName(dataDir))
If dataAbs = rootAbs Or Left(dataAbs, Len(rootAbs) + 1) = rootAbs & "\" Or _
   Left(rootAbs, Len(dataAbs) + 1) = dataAbs & "\" Then
    MsgBox "数据目录不能与程序目录相同、互相包含或位于程序目录内。没有保存任何设置。", vbCritical, "AI 工作台首次设置"
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

Set shortcut = shell.CreateShortcut(desktop & "\AI 工作台.lnk")
shortcut.TargetPath = target
shortcut.Arguments = Chr(34) & root & "\start_aiworkspace.vbs" & Chr(34)
shortcut.WorkingDirectory = root
shortcut.Description = "后台启动 AIWorkSpace 并打开工作台网页"
shortcut.Save

Set shortcut = shell.CreateShortcut(desktop & "\关闭 AI 工作台.lnk")
shortcut.TargetPath = target
shortcut.Arguments = Chr(34) & root & "\stop_aiworkspace.vbs" & Chr(34)
shortcut.WorkingDirectory = root
shortcut.Description = "安全停止由桌面快捷方式启动的 AIWorkSpace 服务"
shortcut.Save

MsgBox "设置完成，已在桌面创建两个快捷方式：" & vbCrLf & _
       "1. AI 工作台" & vbCrLf & _
       "2. 关闭 AI 工作台" & vbCrLf & vbCrLf & _
       "数据目录：" & fso.GetAbsolutePathName(dataDir) & vbCrLf & _
       "本机设置保存在 LocalAppData，不会同步到 Google Drive 或提交到 GitHub。", _
       vbInformation, "AI 工作台首次设置"

Function JsonEscape(value)
    value = Replace(value, "\", "\\")
    value = Replace(value, Chr(34), "\" & Chr(34))
    value = Replace(value, vbCr, "\r")
    value = Replace(value, vbLf, "\n")
    JsonEscape = value
End Function
