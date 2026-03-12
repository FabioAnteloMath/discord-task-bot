import json
import logging
import discord
from discord.ext import commands, tasks
from datetime import datetime
from pathlib import Path
from commands.tasks import _enviar_dm_com_retry

logger = logging.getLogger("TaskBot.Scheduler")

# Mesmo caminho usado em commands/tasks.py
TASKS_FILE = Path("data/tasks.json")


def load_tasks() -> list:
    """Lê o arquivo JSON e retorna a lista de tarefas."""
    if not TASKS_FILE.exists() or TASKS_FILE.stat().st_size == 0:
        return []
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tasks(tasks_list: list) -> None:
    """Salva a lista de tarefas no arquivo JSON."""
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks_list, f, ensure_ascii=False, indent=2)


class SchedulerCog(commands.Cog):
    """Cog responsável por verificar e enviar lembretes automáticos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_reminders.start()  # Inicia o loop assim que o Cog é carregado

    def cog_unload(self):
        """Chamado automaticamente quando o Cog é removido. Cancela o loop."""
        self.check_reminders.cancel()

    @tasks.loop(minutes=1)
    async def check_reminders(self):
        """Verifica todas as tarefas e envia DM para as que venceram."""
        agora = datetime.now()
        task_list = load_tasks()
        houve_alteracao = False

        for tarefa in task_list:
            if tarefa["enviado"]:
                continue

            data_hora = datetime.fromisoformat(tarefa["data_hora"])

            if agora >= data_hora:
                # Tenta buscar o canal de fallback (caso DM seja bloqueada)
                # Tarefas antigas podem nao ter channel_id — tratamos com try/except
                try:
                    canal_fallback = self.bot.get_channel(int(tarefa["channel_id"]))
                except (KeyError, ValueError, TypeError):
                    canal_fallback = None

                # --- Notifica o criador da tarefa ---
                await self._notificar(
                    user_id=tarefa["user_id"],
                    mensagem=(
                        f"\u23f0 **Lembrete!**\n"
                        f"**Tarefa:** {tarefa['descricao']}\n"
                        f"**Agendado para:** {data_hora.strftime('%d/%m/%Y as %H:%M')}"
                    ),
                    canal_fallback=canal_fallback,
                    tarefa_id=tarefa["id"]
                )

                # --- Notifica cada membro relacionado ---
                for membro_id in tarefa.get("membros", []):
                    await self._notificar(
                        user_id=membro_id,
                        mensagem=(
                            f"\u23f0 **Lembrete de tarefa compartilhada!**\n"
                            f"**Tarefa:** {tarefa['descricao']}\n"
                            f"**Agendado para:** {data_hora.strftime('%d/%m/%Y as %H:%M')}"
                        ),
                        canal_fallback=canal_fallback,
                        tarefa_id=tarefa["id"]
                    )

                tarefa["enviado"] = True
                houve_alteracao = True
                logger.info(f"[Lembrete concluido] ID: {tarefa['id']}")

        if houve_alteracao:
            save_tasks(task_list)

    async def _notificar(self, user_id: str, mensagem: str, canal_fallback, tarefa_id: str):
        """Delega ao helper compartilhado com retry automático em erros 5xx."""
        await _enviar_dm_com_retry(
            bot=self.bot,
            user_id=user_id,
            mensagem=mensagem,
            canal_fallback=canal_fallback,
        )

    @check_reminders.before_loop
    async def before_check(self):
        """Executado antes do loop iniciar.
        Garante que o bot esteja totalmente conectado antes de começar a verificar tarefas."""
        await self.bot.wait_until_ready()


# Função obrigatória chamada pelo bot.load_extension()
async def setup(bot: commands.Bot):
    await bot.add_cog(SchedulerCog(bot))
