import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Lê o arquivo .env e carrega as variáveis (ex: TOKEN)
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Intents: declara quais eventos o bot quer "escutar"
intents = discord.Intents.default()
intents.message_content = True  # Permite ler conteúdo de mensagens
intents.members = True          # Permite ver membros do servidor

# Cria a instância principal do bot
bot = commands.Bot(command_prefix="!", intents=intents)


# setup_hook roda antes do on_ready — ideal para carregar módulos (Cogs)
async def setup_hook():
    await bot.load_extension("commands.tasks")   # Carrega os comandos de tarefas
    await bot.load_extension("utils.scheduler")  # Carrega o sistema de lembretes
    print("Módulos carregados com sucesso.")

bot.setup_hook = setup_hook  # Registra a função no bot


# Evento disparado quando o bot se conecta ao Discord com sucesso
@bot.event
async def on_ready():
    await bot.tree.sync()  # Registra os slash commands no Discord
    print(f"Bot conectado como: {bot.user} (ID: {bot.user.id})")
    print("Slash commands sincronizados!")


# Inicia o bot — essa linha mantém o programa rodando
bot.run(TOKEN)