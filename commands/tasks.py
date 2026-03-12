import json
import uuid
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from pathlib import Path

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
        # Aceita tanto ano com 4 dígitos (20/03/2026) quanto 2 dígitos (20/03/26)
        data_hora = None
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
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

        await interaction.response.send_message(
            f"✅ Tarefa agendada!\n"
            f"**ID:** `{nova_tarefa['id']}`\n"
            f"**Descrição:** {descricao}\n"
            f"**Data/Hora:** {data_hora.strftime('%d/%m/%Y às %H:%M')}"
            f"{linha_membros}",
            ephemeral=True
        )

        # Notifica imediatamente cada membro mencionado via DM
        # Isso ocorre logo após salvar a tarefa, informando que foram incluídos
        # Usamos interaction.client para acessar o bot de dentro do Cog
        for mid in ids_membros:
            try:
                membro = await interaction.client.fetch_user(int(mid))
                await membro.send(
                    f"\U0001f4cc **Voce foi incluido em uma tarefa!**\n"
                    f"**Criado por:** {interaction.user.display_name}\n"
                    f"**Tarefa:** {descricao}\n"
                    f"**Agendado para:** {data_hora.strftime('%d/%m/%Y as %H:%M')}\n"
                    f"Voce recebera um lembrete automatico no horario agendado."
                )
                import logging
                logging.getLogger("TaskBot").info(f"[Notificacao criacao] Membro {mid} notificado via DM")
            except discord.Forbidden:
                # DM bloqueada — menciona no canal onde a task foi criada
                try:
                    canal = interaction.client.get_channel(interaction.channel_id)
                    if canal:
                        await canal.send(
                            f"<@{mid}> voce foi incluido na tarefa **{descricao}** "
                            f"agendada para {data_hora.strftime('%d/%m/%Y as %H:%M')} "
                            f"por {interaction.user.display_name}."
                        )
                except Exception:
                    pass
            except Exception as e:
                import logging
                logging.getLogger("TaskBot").error(f"Erro ao notificar membro {mid} na criacao: {e}")

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


# Função obrigatória chamada pelo bot.load_extension()
# O discord.py procura por essa função ao carregar um Cog
async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))
