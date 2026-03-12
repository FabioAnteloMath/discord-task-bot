import json
import discord
from discord.ext import commands, tasks
from datetime import datetime
from pathlib import Path

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

    # @tasks.loop: decorator do discord.py que cria um loop assíncrono periódico
    # minutes=1 significa que check_reminders() é executado a cada 1 minuto
    @tasks.loop(minutes=1)
    async def check_reminders(self):
        """Verifica todas as tarefas e envia DM para as que venceram."""
        agora = datetime.now()
        task_list = load_tasks()
        houve_alteracao = False  # Flag para evitar salvar o JSON desnecessariamente

        for tarefa in task_list:
            # Pula tarefas cujo lembrete já foi enviado
            if tarefa["enviado"]:
                continue

            # Converte a string ISO de volta para datetime para comparar
            data_hora = datetime.fromisoformat(tarefa["data_hora"])

            # Se o horário atual é igual ou posterior ao agendado, envia o lembrete
            if agora >= data_hora:
                try:
                    # fetch_user() busca o perfil do usuário pelo ID numérico
                    # Necessário para enviar DM (Direct Message) fora de um servidor
                    user = await self.bot.fetch_user(int(tarefa["user_id"]))
                    await user.send(
                        f"⏰ **Lembrete!**\n"
                        f"**Tarefa:** {tarefa['descricao']}\n"
                        f"**Agendado para:** {data_hora.strftime('%d/%m/%Y às %H:%M')}"
                    )

                    # Notifica cada membro relacionado à tarefa
                    # .get("membros", []) garante compatibilidade com tarefas antigas (sem esse campo)
                    for membro_id in tarefa.get("membros", []):
                        try:
                            membro = await self.bot.fetch_user(int(membro_id))
                            await membro.send(
                                f"⏰ **Lembrete de tarefa compartilhada!**\n"
                                f"**Tarefa:** {tarefa['descricao']}\n"
                                f"**Agendado para:** {data_hora.strftime('%d/%m/%Y às %H:%M')}\n"
                                f"**Criado por:** {user.display_name}"
                            )
                            print(f"[Lembrete membro] ID: {tarefa['id']} → Membro: {membro_id}")
                        except discord.Forbidden:
                            # Membro bloqueou DMs — continua para o próximo sem travar
                            print(f"[DM bloqueada - membro] ID: {tarefa['id']} → Membro: {membro_id}")
                        except Exception as e:
                            print(f"[Erro membro] ID: {tarefa['id']} → Membro: {membro_id} → {e}")

                    tarefa["enviado"] = True  # Marca para não enviar novamente
                    houve_alteracao = True
                    print(f"[Lembrete enviado] ID: {tarefa['id']} → Usuário: {tarefa['user_id']}")

                except discord.Forbidden:
                    # Erro 403: o usuário bloqueou DMs ou não está no servidor
                    # Marcamos como enviado para não ficar tentando em loop
                    tarefa["enviado"] = True
                    houve_alteracao = True
                    print(f"[DM bloqueada] ID: {tarefa['id']} → Usuário: {tarefa['user_id']}")

                except Exception as e:
                    # Captura qualquer outro erro inesperado sem travar o loop
                    print(f"[Erro no lembrete] ID: {tarefa['id']} → {e}")

        # Só salva o arquivo se houve alguma mudança (otimização de I/O)
        if houve_alteracao:
            save_tasks(task_list)

    @check_reminders.before_loop
    async def before_check(self):
        """Executado antes do loop iniciar.
        Garante que o bot esteja totalmente conectado antes de começar a verificar tarefas."""
        await self.bot.wait_until_ready()


# Função obrigatória chamada pelo bot.load_extension()
async def setup(bot: commands.Bot):
    await bot.add_cog(SchedulerCog(bot))
