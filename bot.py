import asyncio
import os
import ssl
import certifi
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Le o arquivo .env e carrega as variaveis (ex: TOKEN)
load_dotenv()
TOKEN = os.getenv('TOKEN')

# Intents: declara quais eventos o bot quer escutar
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


async def main():
    # Correcao SSL para Windows com Python 3.14
    # aiohttp.TCPConnector PRECISA ser criado dentro de um loop assincrono
    # Por isso usamos asyncio.run(main()) ao inves de bot.run()
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    bot = commands.Bot(command_prefix="!", intents=intents, connector=connector)

    async def setup_hook():
        await bot.load_extension("commands.tasks")
        await bot.load_extension("utils.scheduler")
        print("Modulos carregados com sucesso.")

    bot.setup_hook = setup_hook

    @bot.event
    async def on_ready():
        await bot.tree.sync()
        print(f"Bot conectado como: {bot.user} (ID: {bot.user.id})")
        print("Slash commands sincronizados!")

    async with bot:
        await bot.start(TOKEN)


asyncio.run(main())
