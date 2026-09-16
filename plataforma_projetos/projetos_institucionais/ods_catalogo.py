"""Catálogo único das ODS usadas pela plataforma."""

import os
from pathlib import Path

from django.conf import settings
from django.core.files import File
from .models import ODS


ODS_PADRAO = (
    (1, 'Erradicação da Pobreza'),
    (2, 'Fome Zero e Agricultura Sustentável'),
    (3, 'Saúde e Bem-Estar'),
    (4, 'Educação de Qualidade'),
    (5, 'Igualdade de Gênero'),
    (6, 'Água Potável e Saneamento'),
    (7, 'Energia Limpa e Acessível'),
    (8, 'Trabalho Decente e Crescimento Econômico'),
    (9, 'Indústria, Inovação e Infraestrutura'),
    (10, 'Redução das Desigualdades'),
    (11, 'Cidades e Comunidades Sustentáveis'),
    (12, 'Consumo e Produção Responsáveis'),
    (13, 'Ação Contra a Mudança Global do Clima'),
    (14, 'Vida na Água'),
    (15, 'Vida Terrestre'),
    (16, 'Paz, Justiça e Instituições Eficazes'),
    (17, 'Parcerias e Meios de Implementação'),
)


def normalizar_ods_padrao():
    """Reutiliza ODS existentes, corrige seus rótulos e elimina duplicatas equivalentes."""
    principais = []
    duplicatas_removidas = 0

    for numero, titulo_base in ODS_PADRAO:
        titulo_numerado = f'ODS {numero} - {titulo_base}'
        candidatos = list(
            ODS.objects.filter(titulo__in=[titulo_base, titulo_numerado]).order_by('pk')
        )

        principal = next(
            (ods for ods in candidatos if ods.titulo == titulo_base),
            None,
        ) or (candidatos[0] if candidatos else ODS.objects.create(titulo=titulo_numerado))

        if principal.titulo != titulo_numerado:
            principal.titulo = titulo_numerado
            principal.save(update_fields=['titulo'])

        if not principal.imagem:
            nome_imagem = f'ods_imagens/SDG-{numero}.png'
            origem = Path(settings.BASE_DIR) / 'media' / nome_imagem
            if origem.exists():
                if os.environ.get('CLOUDINARY_URL'):
                    with origem.open('rb') as arquivo:
                        principal.imagem.save(
                            f'SDG-{numero}.png',
                            File(arquivo),
                            save=False,
                        )
                else:
                    principal.imagem.name = nome_imagem
                principal.save(update_fields=['imagem'])

        for duplicata in candidatos:
            if duplicata.pk == principal.pk:
                continue
            for projeto in duplicata.projeto_set.all():
                projeto.ods.add(principal)
                projeto.ods.remove(duplicata)
            duplicata.delete()
            duplicatas_removidas += 1

        principais.append(principal)

    return principais, duplicatas_removidas
