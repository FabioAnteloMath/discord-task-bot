# 📅 Discord Task Bot

Bot de tarefas e lembretes para Discord desenvolvido em Python.  
Permite agendar compromissos diretamente pelo chat e receber lembretes automáticos via DM no horário agendado.

---

## ✨ Funcionalidades

| Comando | Descrição |
|---|---|
| `/agendar [data] [hora] [descrição] (membros)` | Agenda um novo compromisso (membros são opcionais) |
| `/listar` | Lista todas as suas tarefas pendentes |
| `/cancelar [id]` | Remove uma tarefa pelo ID |
| `/editar [id] [nova descrição]` | Atualiza a descrição de uma tarefa |
| `/enviar [membros] [mensagem]` | Envia mensagem direta para membros mencionados |

---

## 🛠️ Tecnologias utilizadas

- **Python 3.11+**
- **discord.py 2.x** — biblioteca principal para bots Discord
- **python-dotenv** — carregamento seguro do token via `.env`
- **JSON** — armazenamento local das tarefas
- **aiohttp** — requisições HTTP assíncronas (necessário para discord.py)
- **truststore** — (opcional) para corrigir problemas de SSL/TLS no Windows
- **keep_alive.py** — servidor HTTP mínimo para manter o bot online no Replit

---

## 📁 Estrutura do projeto

```
discord-task-bot/
├── bot.py                  # Ponto de entrada — inicializa o bot
├── commands/
│   ├── __init__.py
│   └── tasks.py            # Slash commands (/agendar, /listar, /cancelar, /editar)
├── data/
│   └── tasks.json          # Armazenamento das tarefas (não versionado)
├── utils/
│   ├── __init__.py
│   └── scheduler.py        # Loop de verificação e envio de lembretes
├── keep_alive.py           # Servidor HTTP para Replit (evita bot offline)
├── .replit                 # Configuração de execução automática no Replit
├── .env                    # Token do bot (nunca subir ao GitHub)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Como rodar localmente

### 1. Clone o repositório
```bash
git clone https://github.com/SEU_USUARIO/discord-task-bot.git
cd discord-task-bot
```

### 2. Crie e ative o ambiente virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

> 💡 Se rodar no Windows e tiver problemas de SSL/TLS (ex: erro ao conectar no Discord), instale o pacote `truststore`:
> ```bash
> pip install truststore
> ```
> O bot já detecta e usa automaticamente se necessário.

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```
> Inclui: `discord.py`, `python-dotenv`, `aiohttp`, (opcional: `truststore`)

### 4. Configure o token

Crie um arquivo `.env` na raiz do projeto:
```
TOKEN=seu_token_do_discord_aqui
```

> ⚠️ Nunca compartilhe ou suba o token ao GitHub.  
> Obtenha o token em: [discord.com/developers/applications](https://discord.com/developers/applications)

### 5. Inicie o bot
```bash
python bot.py
```
> 💡 No Replit, o arquivo `keep_alive.py` é usado para manter o bot online 24/7. O arquivo `.replit` garante execução automática.

Se tudo estiver correto, você verá:
```
Módulos carregados com sucesso.
Bot conectado como: TaskBot#XXXX (ID: ...)
Slash commands sincronizados!
```

---

## 💬 Exemplo de uso

```
/agendar 15/03/2026 14:30 Reunião com a equipe
```
```
✅ Tarefa agendada!
ID: a1b2c3d4
Descrição: Reunião com a equipe
Data/Hora: 15/03/2026 às 14:30
```

No horário agendado, o bot envia automaticamente uma DM:
```
⏰ Lembrete!
Tarefa: Reunião com a equipe
Agendado para: 15/03/2026 às 14:30
```

---

## ☁️ Deploy no Replit

1. Importe o repositório GitHub no [Replit](https://replit.com)
2. Em **Secrets**, adicione a variável `TOKEN` com o valor do seu token
3. O arquivo `keep_alive.py` inicia um servidor HTTP para evitar que o bot "durma".
4. O arquivo `.replit` garante que o comando correto seja executado.
5. Clique em **Run** — o bot ficará online 24/7

---

## 🔒 Segurança

- O token do bot fica exclusivamente no arquivo `.env` (local) ou nos Secrets do Replit (nuvem)
- O arquivo `.env` e `data/tasks.json` estão listados no `.gitignore` e nunca são enviados ao GitHub
- Cada usuário só consegue ver, editar e cancelar as **suas próprias** tarefas
- O bot detecta ambiente (Replit ou local) e ajusta configurações de SSL/TLS automaticamente

---

## 📌 Roadmap — próximas funcionalidades

- [ ] Comando `/hoje` — lista tarefas do dia atual
- [ ] Suporte a tarefas recorrentes (diárias, semanais)
- [ ] Linguagem natural: *"agendar reunião amanhã às 15h"*
- [ ] Migração para SQLite para suporte a maior volume de dados
- [ ] Integração com Google Calendar
- [x] Adicionar membros relacionados a uma tarefa (ex: mencionar participantes de uma reunião)

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
