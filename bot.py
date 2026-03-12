import asyncio
import os
import logging
import traceback
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("TaskBot")

load_dotenv()
TOKEN = os.getenv('TOKEN')

# REPL_ID é uma variável de ambiente que só existe dentro do Replit
# Usamos isso para saber onde o bot está rodando
ON_REPLIT = bool(os.getenv('REPL_ID'))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# No Replit, o bot precisa de um servidor HTTP ativo para não "dormir"
# O plano gratuito encerra processos inativos — o keep_alive resolve isso
if ON_REPLIT:
    from keep_alive import keep_alive
    keep_alive()
    logger.info("Servidor keep-alive iniciado (modo Replit)")


async def main():
    if ON_REPLIT:
        # Replit roda em Linux com SSL correto — não precisa de connector especial
        connector = None
    else:
        # Windows local com antivírus/firewall que intercepta TLS
        # ssl=False desativa verificação — seguro apenas em desenvolvimento local
        connector = aiohttp.TCPConnector(ssl=False)

    bot = commands.Bot(command_prefix="!", intents=intents, connector=connector)

    async def setup_hook():
        await bot.load_extension("commands.tasks")
        await bot.load_extension("utils.scheduler")
        logger.info("Modulos carregados com sucesso.")

    bot.setup_hook = setup_hook

    @bot.event
    async def on_ready():
        await bot.tree.sync()
        logger.info(f"Bot conectado como: {bot.user} (ID: {bot.user.id})")
        logger.info("Slash commands sincronizados!")

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        comando = interaction.command.name if interaction.command else "desconhecido"
        usuario = f"{interaction.user} (ID: {interaction.user.id})"
        tb = traceback.format_exc()
        logger.error(
            f"Erro no comando /{comando} | Usuario: {usuario}\n"
            f"Tipo: {type(error).__name__}\nMotivo: {error}\nTraceback:\n{tb}"
        )
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"Aguarde {error.retry_after:.1f}s antes de usar este comando novamente."
        elif isinstance(error, app_commands.MissingPermissions):
            msg = "Voce nao tem permissao para usar este comando."
        elif isinstance(error, app_commands.BotMissingPermissions):
            msg = "O bot nao tem as permissoes necessarias."
        else:
            msg = (
                f"Ocorreu um erro ao executar `/{comando}`.\n"
                f"**Tipo:** `{type(error).__name__}`\n"
                f"**Motivo:** {error}"
            )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"\u274c {msg}", ephemeral=True)
            else:
                await interaction.response.send_message(f"\u274c {msg}", ephemeral=True)
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem de erro ao usuario: {e}")

    if connector:
        async with bot:
            await bot.start(TOKEN)
    else:
        await bot.start(TOKEN)


asyncio.run(main())
