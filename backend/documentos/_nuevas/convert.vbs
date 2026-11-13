Dim wd, doc, fso, f
Set fso = CreateObject("Scripting.FileSystemObject")
Set wd = CreateObject("Word.Application")
wd.Visible = False
wd.DisplayAlerts = 0
For Each f In fso.GetFolder(fso.GetAbsolutePathName("..\plantillas_sumoto")).Files
    If LCase(fso.GetExtensionName(f.Name)) = "doc" Then
        If Left(f.Name,1)="3" Or Left(f.Name,1)="5" Or Left(f.Name,1)="6" Then
            Set doc = wd.Documents.Open(f.Path, False, True)
            doc.SaveAs2 fso.GetAbsolutePathName(".\" & fso.GetBaseName(f.Name) & ".docx"), 16
            doc.Close False
            WScript.Echo "OK " & f.Name
        End If
    End If
Next
wd.Quit
