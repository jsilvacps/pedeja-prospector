# PedeJá Prospector v1.0

Sistema desktop para prospecção comercial do PedeJá.

## Recursos
- Busca de estabelecimentos por segmento, estado e cidade usando Google Places API.
- Coleta de nome, endereço, telefone público, site e link do Google Maps.
- Exportação para Excel e CSV.
- Editor de mensagem comercial.
- Botão para abrir WhatsApp Web/App com mensagem pronta para envio manual.
- Banco local SQLite para histórico dos leads.

## Instalação para testar

Abra o PowerShell na pasta do projeto:

```powershell
cd C:\Projetos\PedeJaProspector
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Caso o PowerShell bloqueie o Activate.ps1:

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

## Como gerar o executável

```powershell
cd C:\Projetos\PedeJaProspector
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

O EXE será criado em:

```text
dist\PedeJaProspector.exe
```

## Como gerar setup instalador

Instale o Inno Setup no Windows e execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_setup.ps1
```

O instalador será criado na pasta `installer_output`.

## Google Places API

Você precisa criar uma chave no Google Cloud com Places API habilitada.
Cole a chave no campo "Google Places API Key" dentro do programa.

## Observação de uso responsável

O sistema abre o WhatsApp com a mensagem pronta, mas o envio é manual. Evite disparos em massa e mantenha uma abordagem comercial respeitosa.
