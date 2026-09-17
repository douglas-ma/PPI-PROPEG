"""Catálogo institucional de centros e cursos presenciais da UFAC.

Fontes consultadas em setembro de 2026:
- https://www.ufac.br/site/cursos
- https://www.ufac.br/site/ufac/prograd/cursos/rio-branco
- https://www.ufac.br/site/cursos/cmulti
"""

CENTROS_UFAC = (
    {
        'sigla': 'CCBN',
        'nome': 'CCBN - Centro Acadêmico de Ciências Biológicas e da Natureza',
        'email': 'ccbn@ufac.br',
    },
    {
        'sigla': 'CCET',
        'nome': 'CCET - Centro Acadêmico de Ciências Exatas e Tecnológicas',
        'email': 'ccet@ufac.br',
    },
    {
        'sigla': 'CCJSA',
        'nome': 'CCJSA - Centro Acadêmico de Ciências Jurídicas e Sociais Aplicadas',
        'email': 'ccjsa@ufac.br',
    },
    {
        'sigla': 'CCSD',
        'nome': 'CCSD - Centro Acadêmico de Ciências da Saúde e do Desporto',
        'email': 'ccsd@ufac.br',
    },
    {
        'sigla': 'CELA',
        'nome': 'CELA - Centro Acadêmico de Educação, Letras e Artes',
        'email': 'cela@ufac.br',
    },
    {
        'sigla': 'CFCH',
        'nome': 'CFCH - Centro Acadêmico de Filosofia e Ciências Humanas',
        'email': 'cfch@ufac.br',
    },
    {
        'sigla': 'CEL',
        'nome': 'CEL - Centro Acadêmico de Educação e Letras (Campus Floresta)',
        'email': 'cel.ufac@gmail.com',
    },
    {
        'sigla': 'CMULTI',
        'nome': 'CMULTI - Centro Acadêmico Multidisciplinar (Campus Floresta)',
        'email': 'cmulti@ufac.br',
    },
)


CURSOS_UFAC = (
    # Campus Rio Branco - CCBN
    ('CCBN', 'Bacharelado em Engenharia Agronômica'),
    ('CCBN', 'Bacharelado em Engenharia Florestal'),
    ('CCBN', 'Bacharelado em Física'),
    ('CCBN', 'Bacharelado em Medicina Veterinária'),
    ('CCBN', 'Licenciatura em Ciências Biológicas'),
    ('CCBN', 'Licenciatura em Física'),
    ('CCBN', 'Licenciatura em Química'),

    # Campus Rio Branco - CCET
    ('CCET', 'Bacharelado em Engenharia Civil'),
    ('CCET', 'Bacharelado em Engenharia Elétrica'),
    ('CCET', 'Bacharelado em Sistemas de Informação'),
    ('CCET', 'Licenciatura em Matemática'),

    # Campus Rio Branco - CCJSA
    ('CCJSA', 'Bacharelado em Ciências Contábeis'),
    ('CCJSA', 'Bacharelado em Ciências Econômicas'),
    ('CCJSA', 'Bacharelado em Direito'),

    # Campus Rio Branco - CCSD
    ('CCSD', 'Bacharelado em Educação Física'),
    ('CCSD', 'Bacharelado em Enfermagem'),
    ('CCSD', 'Bacharelado em Medicina'),
    ('CCSD', 'Bacharelado em Nutrição'),
    ('CCSD', 'Bacharelado em Saúde Coletiva'),
    ('CCSD', 'Licenciatura em Educação Física'),

    # Campus Rio Branco - CELA
    ('CELA', 'Bacharelado em Teatro'),
    ('CELA', 'Licenciatura em Letras - Espanhol'),
    ('CELA', 'Licenciatura em Letras - Francês'),
    ('CELA', 'Licenciatura em Letras - Inglês'),
    ('CELA', 'Licenciatura em Letras - Libras'),
    ('CELA', 'Licenciatura em Letras - Língua Portuguesa'),
    ('CELA', 'Licenciatura em Música'),
    ('CELA', 'Licenciatura em Pedagogia'),
    ('CELA', 'Licenciatura em Teatro'),

    # Campus Rio Branco - CFCH
    ('CFCH', 'Bacharelado em Ciências Sociais'),
    ('CFCH', 'Bacharelado em Geografia'),
    ('CFCH', 'Bacharelado em História'),
    ('CFCH', 'Bacharelado em Jornalismo'),
    ('CFCH', 'Bacharelado em Psicologia'),
    ('CFCH', 'Licenciatura em Ciências Sociais'),
    ('CFCH', 'Licenciatura em Filosofia'),
    ('CFCH', 'Licenciatura em Geografia'),
    ('CFCH', 'Licenciatura em História'),

    # Campus Floresta - CEL
    ('CEL', 'Licenciatura em Formação Docente Indígena'),
    ('CEL', 'Licenciatura em Letras - Espanhol'),
    ('CEL', 'Licenciatura em Letras - Inglês'),
    ('CEL', 'Licenciatura em Letras - Língua Portuguesa'),
    ('CEL', 'Licenciatura em Pedagogia'),

    # Campus Floresta - CMULTI
    ('CMULTI', 'Bacharelado em Ciências Biológicas'),
    ('CMULTI', 'Bacharelado em Direito'),
    ('CMULTI', 'Bacharelado em Enfermagem'),
    ('CMULTI', 'Bacharelado em Engenharia Agronômica'),
    ('CMULTI', 'Bacharelado em Engenharia Florestal'),
    ('CMULTI', 'Licenciatura em Ciências Biológicas'),
)


def criar_catalogo_ufac(CentroLotacao, CursoGraduacao, *, limpar=False):
    """Cria o catálogo e devolve um mapa de centros pela sigla."""
    if limpar:
        CursoGraduacao.objects.all().delete()
        CentroLotacao.objects.all().delete()

    centros = {}
    for dados in CENTROS_UFAC:
        centro = CentroLotacao.objects.filter(nome=dados['nome']).first()
        if centro is None:
            centro = CentroLotacao.objects.filter(nome=dados['sigla']).first()
        if centro is None:
            centro = CentroLotacao.objects.filter(
                nome__startswith=f"{dados['sigla']} - ",
            ).first()
        if centro is None:
            centro = CentroLotacao.objects.create(
                nome=dados['nome'],
                email=dados['email'],
            )
        else:
            centro.nome = dados['nome']
            centro.email = dados['email']
            centro.save(update_fields=['nome', 'email'])
        centros[dados['sigla']] = centro

    for sigla, nome_curso in CURSOS_UFAC:
        if not CursoGraduacao.objects.filter(
            nome=nome_curso,
            centro_lotacao=centros[sigla],
        ).exists():
            CursoGraduacao.objects.create(
                nome=nome_curso,
                centro_lotacao=centros[sigla],
            )

    return centros
