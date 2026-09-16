import re
import unicodedata

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class DocumentoProjetoError(Exception):
    """Erro legível para problemas ao processar o documento do projeto."""


class DocumentoSemTextoError(DocumentoProjetoError):
    """O PDF não contém texto selecionável suficiente para ser considerado digital."""


LIMITES_CAMPOS = {
    'resumo': 1500,
    'palavras_chave': 255,
}


SECOES_PROJETO = {
    'resumo': {
        'resumo',
    },
    'palavras_chave': {
        'palavras chave',
        'palavra chave',
        'keywords',
    },
    'introducao': {
        'introducao',
        'justificativa',
        'introducao e justificativa',
        'contextualizacao e justificativa',
    },
    'objetivo_geral': {
        'objetivo geral',
    },
    'objetivos_especificos': {
        'objetivos especificos',
        'objetivo especifico',
    },
    'metodologia': {
        'metodologia',
        'metodos',
        'materiais e metodos',
        'procedimentos metodologicos',
    },
    'resultados': {
        'resultados esperados',
        'resultados e impactos esperados',
        'resultados',
        'produtos e resultados esperados',
    },
    'parcerias': {
        'parcerias',
        'instituicoes parceiras',
        'instituicoes envolvidas',
    },
    'referencias': {
        'referencias',
        'referencias bibliograficas',
        'bibliografia',
    },
}


SECOES_SOMENTE_LIMITE = {
    'objetivos',
    'cronograma',
    'orcamento',
    'recursos necessarios',
    'equipe',
    'plano de trabalho',
    'consideracoes finais',
    'conclusao',
    'anexos',
    'apendices',
}


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(caractere for caractere in texto if not unicodedata.combining(caractere))
    texto = texto.lower().strip()
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def _remover_numeracao_titulo(linha):
    return re.sub(
        r'^\s*(?:(?:\d+(?:\.\d+)*)|(?:[ivxlcdm]+))[\s.\-)–—:]+',
        '',
        linha,
        flags=re.IGNORECASE,
    ).strip()


def _identificar_secao(linha):
    """Retorna (encontrou_titulo, campo, conteúdo após dois-pontos)."""
    linha = _remover_numeracao_titulo(linha.strip())
    if not linha or len(linha) > 140:
        return False, None, ''

    candidatos = [(linha, '')]
    for separador in (':', '–', '—'):
        if separador in linha:
            titulo, conteudo = linha.split(separador, 1)
            candidatos.insert(0, (titulo.strip(), conteudo.strip()))

    for titulo, conteudo in candidatos:
        titulo_normalizado = _normalizar(titulo)
        for campo, nomes in SECOES_PROJETO.items():
            if titulo_normalizado in nomes:
                return True, campo, conteudo
        if titulo_normalizado in SECOES_SOMENTE_LIMITE:
            return True, None, ''

    return False, None, ''


def extrair_texto_pdf_digital(arquivo):
    """Extrai texto selecionável. Não executa OCR em documentos digitalizados."""
    try:
        arquivo.seek(0)
        leitor = PdfReader(arquivo)
        if leitor.is_encrypted:
            try:
                descriptografado = leitor.decrypt('')
            except Exception as erro:
                raise DocumentoProjetoError('O PDF está protegido por senha e não pode ser processado.') from erro
            if not descriptografado:
                raise DocumentoProjetoError('O PDF está protegido por senha e não pode ser processado.')

        if len(leitor.pages) > 200:
            raise DocumentoProjetoError('O documento excede o limite de 200 páginas.')

        paginas = []
        for pagina in leitor.pages:
            paginas.append(pagina.extract_text() or '')
        texto = '\n\n'.join(paginas).strip()
    except DocumentoProjetoError:
        raise
    except PdfReadError as erro:
        raise DocumentoProjetoError('Não foi possível ler o PDF enviado. Verifique se o arquivo está íntegro.') from erro
    except Exception as erro:
        raise DocumentoProjetoError('Não foi possível processar o documento enviado.') from erro
    finally:
        try:
            arquivo.seek(0)
        except Exception:
            pass

    texto_util = re.sub(r'\s+', '', texto)
    if len(texto_util) < 80:
        raise DocumentoSemTextoError(
            'O PDF não possui texto selecionável suficiente. Envie um arquivo nativamente digital, '
            'não uma digitalização ou fotografia de páginas.'
        )
    return texto


def extrair_campos_projeto(texto):
    """Separa o texto pelas seções acadêmicas reconhecidas no documento."""
    secoes = {campo: [] for campo in SECOES_PROJETO}
    campo_atual = None

    for linha in texto.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        linha = linha.strip()
        encontrou_titulo, campo, conteudo = _identificar_secao(linha)
        if encontrou_titulo:
            campo_atual = campo
            if campo_atual and conteudo:
                secoes[campo_atual].append(conteudo)
            continue
        if campo_atual and linha:
            secoes[campo_atual].append(linha)

    resultado = {}
    for campo, linhas in secoes.items():
        conteudo = '\n'.join(linhas).strip()
        conteudo = re.sub(r'\n{3,}', '\n\n', conteudo)
        if not conteudo:
            continue
        limite = LIMITES_CAMPOS.get(campo)
        resultado[campo] = conteudo[:limite].strip() if limite else conteudo

    return resultado
