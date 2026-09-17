from django.core.management.base import BaseCommand
from django.urls import reverse
from datetime import date, timedelta
from projetos_institucionais.models import Projeto
from projetos_institucionais.views import enviar_email_e_notificacao

class Command(BaseCommand):
    help = 'Verifica projetos próximos do fim e envia lembretes para os coordenadores sobre o relatório final.'

    def handle(self, *args, **options):
        hoje = date.today()
        dias_lembrete = [90, 60, 30, 14, 7, 1]

        projetos_ativos = Projeto.objects.filter(status='em_andamento').exclude(relatorios__tipo='final')

        self.stdout.write(self.style.SUCCESS(f'Verificando {projetos_ativos.count()} projetos ativos...'))

        for projeto in projetos_ativos:
            if not projeto.coordenador_id:
                continue
            if projeto.data_fim:
                dias_restantes = (projeto.data_fim - hoje).days

                if dias_restantes in dias_lembrete:
                    self.stdout.write(f'Enviando lembrete para o projeto "{projeto.titulo}" (Faltam {dias_restantes} dias)')
                    
                    coordenador = projeto.coordenador
                    subject = f'Lembrete: O prazo para o projeto "{projeto.titulo}" está terminando!'
                    message = (
                        f'Olá, {coordenador.first_name}!\n\n'
                        f'Este é um lembrete de que o projeto "{projeto.titulo}" está chegando ao fim. Faltam {dias_restantes} dia(s).\n\n'
                        f'Por favor, não se esqueça de submeter o relatório final de atividades na plataforma.'
                    )
                    link_relatorio = reverse('relatorio_lista_projetos')

                    enviar_email_e_notificacao(subject, message, coordenador, link=link_relatorio)

        self.stdout.write(self.style.SUCCESS('Verificação de lembretes concluída.'))
