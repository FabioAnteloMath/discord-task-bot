import asyncio
import json
import logging
import uuid
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("TaskBot")


async def _enviar_dm_com_retry(bot: discord.Client, user_id: str, mensagem: str,
                               canal_fallback=None, tentativas: int = 3) -> None:
    """Tenta enviar DM até `tentativas` vezes em erros 5xx (servidor do Discord).
    Se DM estiver bloqueada (403), menciona no canal de fallback."""
    for tentativa in range(1, tentativas + 1):
        try:
            user = await bot.fetch_user(int(user_id))
            await user.send(mensagem)
            logger.info(f"[DM enviada] -> Usuario: {user_id}")
            return
        except discord.Forbidden:
            # Usuário bloqueou DMs — não adianta tentar de novo
            logger.warning(f"[DM bloqueada] -> Usuario: {user_id} — tentando canal fallback")
            if canal_fallback:
                try:
                    await canal_fallback.send(f"<@{user_id}> {mensagem}")
                    logger.info(f"[Fallback canal] -> Usuario: {user_id}")
                except Exception as e:
                    logger.error(f"[Fallback canal falhou] -> {e}")
            return
        except discord.HTTPException as e:
            # 503 / 5xx: erro temporário do servidor — espera e tenta de novo
            if e.status >= 500 and tentativa < tentativas:
                espera = 2 ** tentativa  # 2s, 4s, 8s
                logger.warning(f"[DM erro {e.status}] Usuario: {user_id} — tentativa {tentativa}/{tentativas}, aguardando {espera}s")
                await asyncio.sleep(espera)
            else:
                logger.error(f"[DM falhou] Usuario: {user_id} — {e.status}: {e.text}")
                return
        except Exception as e:
            logger.error(f"[DM erro inesperado] Usuario: {user_id} — {e}")
            return

# Caminho absoluto para o arquivo de dados, relativo à raiz do projeto
TASKS_FILE = Path("data/tasks.json")


def load_tasks() -> list:
    """Lê o arquivo JSON e retorna a lista de tarefas.
    Retorna lista vazia se o arquivo não existir ou estiver vazio."""
    if not TASKS_FILE.exists() or TASKS_FILE.stat().st_size == 0:
        return []
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tasks(tasks: list) -> None:
    """Salva a lista de tarefas no arquivo JSON com indentação para legibilidade."""
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


class TasksCog(commands.Cog):
    """Cog com todos os comandos de gerenciamento de tarefas.
    Um Cog é uma classe que agrupa comandos relacionados em um módulo separado."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot  # Guarda referência ao bot para uso nos métodos

    # --- Comando /agendar ---
    @app_commands.command(name="agendar", description="Agenda um novo compromisso ou tarefa")
    @app_commands.describe(
        data="Data no formato DD/MM/AAAA (ex: 15/03/2026)",
        hora="Hora no formato HH:MM (ex: 14:30)",
        descricao="Descrição do compromisso",
        membros="Mencione os membros relacionados (ex: @joao @maria) — opcional"
    )
    async def agendar(self, interaction: discord.Interaction, data: str, hora: str, descricao: str, membros: str = ""):
        # Tenta converter a data e hora informadas para um objeto datetime
        # ORDEM IMPORTA: %y (2 dígitos) antes de %Y, pois %Y aceita qualquer
        # quantidade de dígitos — "26" com %Y vira ano 26 d.C. (passado!).
        # "2026" falha em %y (exige exatamente 2 dígitos) e cai no %Y.
        data_hora = None
        for fmt in ("%d/%m/%y %H:%M", "%d/%m/%Y %H:%M"):
            try:
                data_hora = datetime.strptime(f"{data} {hora}", fmt)
                break
            except ValueError:
                continue

        if data_hora is None:
            await interaction.response.send_message(
                "❌ Formato inválido! Use: `/agendar DD/MM/AAAA HH:MM descrição`\n"
                "Exemplo: `/agendar 15/03/2026 14:30 Reunião com equipe`",
                ephemeral=True
            )
            return

        # Impede agendar no passado
        if data_hora <= datetime.now():
            await interaction.response.send_message(
                "❌ A data/hora informada já passou! Informe um horário futuro.",
                ephemeral=True
            )
            return

        # Extrai os IDs dos membros mencionados a partir do texto
        # O Discord representa menções como <@ID> ou <@!ID> no texto — usamos re para extrair apenas o número
        import re
        ids_membros = re.findall(r"<@!?(\d+)>", membros)

        # Remove o próprio criador da lista de membros para não enviar DM duplicada
        ids_membros = [mid for mid in ids_membros if mid != str(interaction.user.id)]

        # Log diagnóstico: mostra o que chegou no campo membros e o que foi extraído
        # Útil para depurar casos em que o usuário não usou @menção correta
        if membros:
            logger.info(f"[/agendar] membros bruto='{membros}' | ids extraidos={ids_membros}")
            if not ids_membros:
                logger.warning("[/agendar] Campo membros preenchido mas nenhum ID extraido — usuario pode nao ter usado @mencao")

        tasks = load_tasks()

        # Cria o dicionário da nova tarefa
        nova_tarefa = {
            "id": str(uuid.uuid4())[:8],
            "user_id": str(interaction.user.id),
            "guild_id": str(interaction.guild_id),   # ID do servidor — usado como fallback se DM falhar
            "channel_id": str(interaction.channel_id), # ID do canal — para mencionar no canal se DM bloqueada
            "descricao": descricao,
            "data_hora": data_hora.isoformat(),
            "membros": ids_membros,
            "enviado": False
        }

        tasks.append(nova_tarefa)
        save_tasks(tasks)

        # Monta a linha de membros para exibir na confirmação
        linha_membros = ""
        if ids_membros:
            mencoes = " ".join(f"<@{mid}>" for mid in ids_membros)
            linha_membros = f"\n**Membros:** {mencoes}"

        # Avisa quando campo membros foi preenchido mas nenhuma menção válida foi encontrada
        aviso_membros = ""
        if membros and not ids_membros:
            aviso_membros = (
                "\n\n⚠️ **Atenção:** nenhum membro foi reconhecido.\n"
                "Para adicionar membros, use a @menção do Discord "
                "(selecione o nome da lista que aparece ao digitar @)."
            )

        await interaction.response.defer(ephemeral=True)

        # Notifica imediatamente cada membro mencionado via DM
        canal_fallback = interaction.client.get_channel(interaction.channel_id)
        erro_membros = []
        for mid in ids_membros:
            try:
                await _enviar_dm_com_retry(
                    bot=interaction.client,
                    user_id=mid,
                    mensagem=(
                        f"\U0001f4cc **Voce foi incluido em uma tarefa!**\n"
                        f"**Criado por:** {interaction.user.display_name}\n"
                        f"**Tarefa:** {descricao}\n"
                        f"**Agendado para:** {data_hora.strftime('%d/%m/%Y as %H:%M')}\n"
                        f"Voce recebera um lembrete automatico no horario agendado."
                    ),
                    canal_fallback=canal_fallback,
                )
            except Exception as e:
                erro_membros.append(mid)
                logger.error(f"Erro ao notificar membro {mid}: {e}")

        aviso_erro = ""
        if erro_membros:
            aviso_erro = f"\n\n\u26a0\ufe0f N\u00e3o foi poss\u00edvel notificar: {' '.join(f'<@{mid}>' for mid in erro_membros)}."

        await interaction.followup.send(
            f"\u2705 Tarefa agendada!\n"
            f"**ID:** `{nova_tarefa['id']}`\n"
            f"**Descri\u00e7\u00e3o:** {descricao}\n"
            f"**Data/Hora:** {data_hora.strftime('%d/%m/%Y \u00e0s %H:%M')}"
            f"{linha_membros}"
            f"{aviso_membros}"
            f"{aviso_erro}",
            ephemeral=True
        )

    # --- Comando /listar ---
    @app_commands.command(name="listar", description="Lista todas as suas tarefas agendadas")
    async def listar(self, interaction: discord.Interaction):
        tasks = load_tasks()

        # Filtra apenas tarefas do usuário atual que ainda não foram enviadas
        user_tasks = [
            t for t in tasks
            if t["user_id"] == str(interaction.user.id) and not t["enviado"]
        ]

        if not user_tasks:
            await interaction.response.send_message(
                "📭 Você não tem tarefas agendadas.", ephemeral=True
            )
            return

        # Monta a mensagem com todas as tarefas encontradas
        linhas = ["📋 **Suas tarefas agendadas:**\n"]
        for t in user_tasks:
            dt = datetime.fromisoformat(t["data_hora"])  # Converte a string ISO de volta para datetime

            # Monta a linha de membros se existirem
            # .get("membros", []) garante compatibilidade com tarefas antigas (sem o campo)
            membros_ids = t.get("membros", [])
            linha_membros = ""
            if membros_ids:
                mencoes = " ".join(f"<@{mid}>" for mid in membros_ids)
                linha_membros = f"\n  👥 {mencoes}"

            linhas.append(
                f"• `{t['id']}` — **{t['descricao']}**\n"
                f"  🕐 {dt.strftime('%d/%m/%Y às %H:%M')}"
                f"{linha_membros}"
            )

        await interaction.response.send_message("\n".join(linhas), ephemeral=True)

    # --- Comando /cancelar ---
    @app_commands.command(name="cancelar", description="Cancela uma tarefa pelo ID")
    @app_commands.describe(id="O ID da tarefa (use /listar para ver os IDs)")
    async def cancelar(self, interaction: discord.Interaction, id: str):
        tasks = load_tasks()

        # next() busca o primeiro item que corresponda à condição, ou retorna None
        # Verifica tanto o ID quanto o user_id para segurança (ninguém apaga tarefa alheia)
        tarefa = next(
            (t for t in tasks if t["id"] == id and t["user_id"] == str(interaction.user.id)),
            None
        )

        if not tarefa:
            await interaction.response.send_message(
                f"❌ Nenhuma tarefa encontrada com o ID `{id}`.", ephemeral=True
            )
            return

        tasks.remove(tarefa)
        save_tasks(tasks)

        await interaction.response.send_message(
            f"🗑️ Tarefa `{id}` cancelada: **{tarefa['descricao']}**", ephemeral=True
        )

    # --- Comando /editar ---
    @app_commands.command(name="editar", description="Edita a descrição de uma tarefa pelo ID")
    @app_commands.describe(
        id="O ID da tarefa (use /listar para ver os IDs)",
        nova_descricao="A nova descrição para a tarefa"
    )
    async def editar(self, interaction: discord.Interaction, id: str, nova_descricao: str):
        tasks = load_tasks()

        tarefa = next(
            (t for t in tasks if t["id"] == id and t["user_id"] == str(interaction.user.id)),
            None
        )

        if not tarefa:
            await interaction.response.send_message(
                f"❌ Nenhuma tarefa encontrada com o ID `{id}`.", ephemeral=True
            )
            return

        descricao_antiga = tarefa["descricao"]
        tarefa["descricao"] = nova_descricao  # Atualiza diretamente no dicionário (que é referência na lista)
        save_tasks(tasks)

        await interaction.response.send_message(
            f"✏️ Tarefa `{id}` atualizada!\n"
            f"**Antes:** {descricao_antiga}\n"
            f"**Agora:** {nova_descricao}",
            ephemeral=True
        )

    # --- Comando /enviar ---
    @app_commands.command(name="enviar", description="Envia uma mensagem direta para membros mencionados")
    @app_commands.describe(
        membros="Mencione os membros (ex: @joao @maria)",
        mensagem="Mensagem a ser enviada"
    )
    async def enviar(self, interaction: discord.Interaction, membros: str, mensagem: str):
        import re
        ids_membros = re.findall(r"<@!?(\d+)>", membros)
        ids_membros = [mid for mid in ids_membros if mid != str(interaction.user.id)]

        if not ids_membros:
            await interaction.response.send_message(
                "❌ Nenhum membro reconhecido. Use a @menção do Discord.", ephemeral=True
            )
            return

        # defer() reconhece a interação imediatamente (obrigatório em < 3s)
        # Evita erro 40060 quando retries de DM demoram mais que o timeout
        await interaction.response.defer(ephemeral=True)

        canal_fallback = interaction.channel
        erros = []
        for mid in ids_membros:
            try:
                await _enviar_dm_com_retry(
                    bot=interaction.client,
                    user_id=mid,
                    mensagem=mensagem,
                    canal_fallback=canal_fallback,
                )
            except Exception as e:
                erros.append(mid)
                logger.error(f"Erro ao enviar para {mid}: {e}")

        if erros:
            await interaction.followup.send(
                f"⚠️ Enviado, mas não foi possível notificar: {' '.join(f'<@{mid}>' for mid in erros)}.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"✅ Mensagem enviada para: {' '.join(f'<@{mid}>' for mid in ids_membros)}",
                ephemeral=True
            )


# Função obrigatória chamada pelo bot.load_extension()
# O discord.py procura por essa função ao carregar um Cog
async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))
