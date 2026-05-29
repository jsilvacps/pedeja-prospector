PEDEJÁ PROSPECTOR - COMO USAR

1) Instale Python 3.11 ou superior no Windows.
   Importante: marque a opção "Add Python to PATH".

2) Extraia este projeto em:
   C:\Projetos\PedeJaProspector

3) Abra o PowerShell como usuário normal e execute:
   cd C:\Projetos\PedeJaProspector
   .\build_setup.ps1

4) O executável será gerado em:
   C:\Projetos\PedeJaProspector\dist\PedeJa Prospector\PedeJa Prospector.exe

5) Para criar instalador .exe:
   - Instale o Inno Setup
   - Abra o arquivo installer.iss
   - Clique em Compile
   - O setup ficará em: C:\Projetos\PedeJaProspector\setup\PedeJa_Prospector_Setup.exe

6) Primeira abertura:
   - Vá em Arquivo > Configurações
   - Informe sua Google Places API Key
   - Ative no Google Cloud a API: Places API

IMPORTANTE:
Este sistema não faz disparo automático em massa.
Ele abre o WhatsApp com a mensagem pronta para envio manual por clique.
