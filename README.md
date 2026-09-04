# Agenda OneNote

Aplicativo local e offline para transformar arquivos `.txt` em uma agenda visual inspirada no Microsoft OneNote. O sistema organiza notas em cadernos, secoes e paginas, oferece pesquisa, links clicaveis, relatorios e persistencia em JSON.

## Requisitos

- Windows, Linux ou macOS para executar em modo navegador.
- Python 3.10 ou superior.
- Python e `pip` disponiveis no `PATH`.
- Internet apenas durante a instalacao das dependencias. O aplicativo nao precisa de internet depois de iniciado.

## Executar em desenvolvimento

Na raiz do projeto:

```bash
pip install -r requirements.txt
python run.py
```

Abra `http://127.0.0.1:5055` no navegador. Para encerrar, volte ao terminal e pressione `Ctrl+C`.

No Windows, tambem e possivel usar [Agenda.bat](Agenda.bat), que inicia o aplicativo com a configuracao padrao.

## Gerar o executavel

### Windows

O caminho recomendado e executar [build.bat](build.bat) na raiz do projeto:

```powershell
cd C:\caminho\para\AgendaOneNote
.\build.bat
```

O script instala as dependencias e executa o PyInstaller usando [agenda.spec](agenda.spec). O resultado sera:

```text
dist\AgendaOneNote.exe
```

Se o comando `pyinstaller` nao estiver no `PATH`, use o modulo pelo Python instalado:

```powershell
python -m PyInstaller --noconfirm --clean agenda.spec
```

Para gerar uma copia com outro nome na Area de Trabalho:

```powershell
Copy-Item .\dist\AgendaOneNote.exe "$HOME\Desktop\agendaKemel.exe" -Force
```

### Linux e macOS

```bash
pip install -r requirements.txt
bash build.sh
```

O executavel sera criado em `dist/AgendaOneNote`.

### Rebuild limpo

Quando houver alteracoes em templates, arquivos estaticos ou na configuracao do empacotamento, remova os artefatos anteriores antes de compilar novamente:

```powershell
Remove-Item -Recurse -Force .\build, .\dist
python -m PyInstaller --noconfirm --clean agenda.spec
```

## Importar arquivos `.txt`

Coloque os arquivos em `data/entrada_txt`. O aplicativo le automaticamente os arquivos `.txt` dessa pasta e de suas subpastas ao iniciar. O mesmo arquivo nao e duplicado em cada abertura.

Para importar arquivos novos ou alterados sem reiniciar, use **Atualizar interface**. Cada nova versao e importada uma unica vez.

No executavel do Windows, os dados ficam em:

```text
%LocalAppData%\AgendaOneNote\data\entrada_txt
```

Os dados persistentes ficam em `data/notes.json` e `data/notebooks.json`. Relatorios e backups podem ser gerados pela propria aplicacao.

## Formato do arquivo `.txt`

Separe notas com uma linha contendo `---`. Os cabecalhos sao opcionais:

```text
TITULO: Reuniao
IMPORTANCIA: urgente
TAGS: trabalho, produto
CADERNO: Trabalho
SECAO: Reunioes
DATA: 04/09/2026 09:00
PRAZO: 05/09/2026

Texto da nota com https://exemplo.com e email@dominio.com
```

Niveis de importancia aceitos: `urgente`, `alta`, `media` e `baixa`. Tambem sao aceitos `high`, `low`, `[urgente]` e `!!!`.

## Recursos

- Visualizacao em cards com faixa de importancia.
- Pesquisa em tempo real no titulo, conteudo, tags e nome do arquivo.
- Links e e-mails clicaveis no editor.
- Criacao de cadernos, secoes e paginas dentro do app.
- Relatorios em HTML/TXT e persistencia em JSON.
- Escolha do formato de exportacao: no executavel, abre a janela **Salvar como** do Windows; no navegador, usa o download normal.

## Atalhos

- `Ctrl+N`: nova pagina.
- `Ctrl+S`: salvar.
- `Esc`: fechar painel.

## Testes

Execute os testes automatizados com:

```bash
python -m pytest
```

## Seguranca e versionamento

Os arquivos em `data/entrada_txt` podem conter senhas, acessos, e-mails ou outras informacoes pessoais. Eles sao ignorados pelo Git por padrao. Revise tambem os arquivos JSON antes de publica-los, pois eles podem conter o conteudo das notas.

O arquivo `.gitignore` mantem fora do repositorio caches, ambientes virtuais, artefatos do PyInstaller e os `.txt` pessoais importados.
