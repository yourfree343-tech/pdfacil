; Instalador de PDFácil (Inno Setup 6). Lo compila build.py:
;   ISCC.exe /DMyAppVersion=1.4.0 installer\PDFacil.iss
; Se instala por usuario (sin administrador), así las actualizaciones automáticas no piden permisos.
; Este archivo debe guardarse en UTF-8 con BOM (por las tildes); build.py se encarga.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppName "PDFácil"
#define MyAppPublisher "Agencia Daga"
#define MyAppURL "https://github.com/yourfree343-tech/pdfacil"
#define MyAppExe "PDFacil.exe"
#define ProgId "EditorPDF.Document"

[Setup]
; mismo AppId que las versiones «Editor PDF»: así se actualiza la instalación existente
AppId={{6F3B9C2E-8D41-4E7A-9B1C-5A2E7D9F0C43}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
AppCopyright=© 2026 {#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Instalador de {#MyAppName}
DefaultDirName={autopf}\PDFacil
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=PDFacil-{#MyAppVersion}-instalador
SetupIconFile=..\icono.ico
WizardImageFile=asistente.bmp,asistente@2x.bmp
WizardSmallImageFile=asistente_peq.bmp,asistente_peq@2x.bmp
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
ChangesAssociations=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"
Name: "pdfassoc"; Description: "Añadir {#MyAppName} a «Abrir con» para los archivos PDF"; GroupDescription: "Archivos PDF:"

[Files]
Source: "..\dist\PDFacil\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; limpia la versión anterior antes de copiar la nueva
Type: filesandordirs; Name: "{app}\_internal"
; restos del nombre anterior («Editor PDF»)
Type: files; Name: "{app}\EditorPDF.exe"
Type: files; Name: "{autoprograms}\Editor PDF.lnk"
Type: files; Name: "{autodesktop}\Editor PDF.lnk"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; mismas claves que editor_pdf/fileassoc.py (Ajustes > Archivos PDF)
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: ""; ValueData: "Documento PDF"; Flags: uninsdeletekey; Tasks: pdfassoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueName: "FriendlyTypeName"; ValueData: "Documento PDF"; Tasks: pdfassoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExe}"",0"; Tasks: pdfassoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"; Tasks: pdfassoc
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExe}"" ""%1"""; Tasks: pdfassoc
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: pdfassoc
Root: HKA; Subkey: "Software\EditorPDF\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey; Tasks: pdfassoc
Root: HKA; Subkey: "Software\EditorPDF\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Ver, editar, firmar y organizar documentos PDF"; Tasks: pdfassoc
Root: HKA; Subkey: "Software\EditorPDF\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "{#ProgId}"; Tasks: pdfassoc
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: "Software\EditorPDF\Capabilities"; Flags: uninsdeletevalue; Tasks: pdfassoc
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: none; ValueName: "Editor PDF"; Flags: deletevalue

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
; en las actualizaciones automáticas (modo silencioso) vuelve a abrir el programa
Filename: "{app}\{#MyAppExe}"; Flags: nowait; Check: WizardSilent
