import os
import logging
import sqlite3
import requests
from typing import List
from dotenv import load_dotenv
from langchain_core.documents import Document

# Carrega as variáveis de ambiente (.env)
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações globais
NOTION_DATABASE_ID = None
NOTION_TOKEN = os.getenv("NOTION_TOKEN")

# Descobre o caminho dos bancos com base na estrutura de pastas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FACILITE = os.path.join(BASE_DIR, 'facilite', 'banco', 'facilite_auditoria.db')
DB_INPERA = os.path.join(BASE_DIR, 'inpera', 'banco', 'inpera_auditoria.db')

# ===========================================================================
# 1. FUNÇÕES DO MOTOR RAG (NOTION E VETORES)
# ===========================================================================

def buscar_dados_base_conhecimento():
    # Força a recarga do arquivo .env direto do disco para não depender do ciclo do Flask
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    token = os.getenv("NOTION_TOKEN")
    db_id = NOTION_DATABASE_ID 
    
    if not token or not db_id:
        logger.error(f"Configuração ausente. Token: {'OK' if token else 'Vazio'} | DB_ID: {'OK' if db_id else 'Vazio'}")
        return []
        
    logger.info("Conectando à API do Notion para buscar registros reais...")
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, headers=headers, json={})
        if response.status_code == 200:
            dados = response.json().get("results", [])
            logger.info(f"Sucesso! {len(dados)} registros reais importados do Notion.")
            return dados
        else:
            logger.error(f"Erro na API do Notion: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Falha de conexão com o Notion: {e}")
        return []

def preparar_documentos_rag(dados_notion):
    """Transforma os dados brutos do Notion em objetos Document do LangChain."""
    documentos = []
    for pagina in dados_notion:
        texto_pagina = ""
        properties = pagina.get("properties", {})
        
        for prop_name, prop_val in properties.items():
            if prop_val.get("type") == "rich_text":
                text_list = prop_val.get("rich_text", [])
                texto_pagina += f"\n{prop_name}: " + "".join([t.get("plain_text", "") for t in text_list])
            elif prop_val.get("type") == "title":
                title_list = prop_val.get("title", [])
                texto_pagina += f"\nTítulo: " + "".join([t.get("plain_text", "") for t in title_list])
                
        if texto_pagina.strip():
            documentos.append(Document(page_content=texto_pagina))
            
    return documentos

def criar_banco_vetores_local(documentos):
    """Retorna os documentos estruturados para busca local."""
    logger.info("Montando banco vetorial local na memória...")
    return documentos

def buscar_blocos_semanticos(pergunta, banco_vetores):
    """Busca inteligente e tolerante a termos comuns (NFe, NF-e, Nota) nos documentos."""
    if not banco_vetores:
        return []
    
    pergunta_limpa = pergunta.lower().replace("-", "") # Remove traço para bater "nf-e" com "nfe"
    palavras_chave = [p for p in pergunta_limpa.split() if len(p) > 2]
    
    # Se o cara falar sobre Nota ou NF-e, adicionamos termos correlatos para garantir o match
    if "nfe" in pergunta_limpa or "nf-e" in pergunta_limpa or "nota" in pergunta_limpa:
        palavras_chave.extend(["nfe", "nf-e", "nota", "fiscal", "faturamento"])

    blocos_encontrados = []
    
    for doc in banco_vetores:
        conteudo = doc.page_content.lower().replace("-", "")
        # Pontuação de relevância básica baseada em quantas palavras batem
        score = sum(1 for palavra in palavras_chave if palavra in conteudo)
        if score > 0:
            blocos_encontrados.append((score, doc))
            
    # Ordena pelo documento que teve mais acertos (maior score)
    blocos_encontrados.sort(key=lambda x: x[0], reverse=True)
    
    # Se achou blocos relevantes, retorna eles. Se não achou nada, traz os 3 primeiros
    if blocos_encontrados:
        return [doc for score, doc in blocos_encontrados[:3]]
    return banco_vetores[:3]


# ===========================================================================
# 2. CAMADA DE MEMÓRIA VIVA (SQLITE COLETIVO) E RESPOSTA DA IA
# ===========================================================================

def buscar_solucoes_historicas(pergunta: str, sistema: str) -> str:
    """Busca no SQLite conversas passadas sobre o mesmo erro para servir de aprendizado."""
    db_path = DB_FACILITE if sistema == 'facilite' else DB_INPERA
    if not os.path.exists(db_path):
        return ""
        
    try:
        # Pega termos chave da pergunta tirando conectores curtos
        palavras = [p for p in pergunta.split() if len(p) > 3]
        if not palavras:
            return ""
            
        clausulas = " OR ".join(["pergunta LIKE ?"] * len(palavras))
        query = f"SELECT pergunta, resposta FROM log_consultas WHERE {clausulas} ORDER BY id DESC LIMIT 3"
        params = [f"%{p}%" for p in palavras]
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        linhas = cursor.fetchall()
        conn.close()
        
        if not linhas:
            return ""
            
        historico_formatado = "\n--- MEMÓRIA DE CONVERSAS ANTERIORES SOBRE ESTE TEMA ---\n"
        for p_antiga, r_antiga in linhas:
            historico_formatado += f"Pergunta anterior do usuário: {p_antiga}\nResposta aplicada/Solução aceita: {r_antiga}\n\n"
        return historico_formatado
    except Exception:
        return ""

def responder_ticket_suporte(pergunta, chunks, sistema):
    import os
    import google.generativeai as genai
    
    # Transforma a pergunta em minúsculas e limpa espaços
    pergunta_lower = pergunta.lower().strip()
    
    # 1. Tratamento de Saudações Simples (Normalizado para evitar erros de acentuação)
    saudaçoes = ['olá', 'ola', 'oi', 'bom dia', 'boa tarde', 'boa noite', 'opa']
    if pergunta_lower in saudaçoes:
        if sistema == 'facilite':
            return "Olá! Sou o assistente virtual do Facilite Flix. Como posso te ajudar com o ERP hoje?"
        else:
            return "Olá! Sou o assistente virtual do Inpera Flix. Em que posso te ajudar com o sistema hoje?"
            
    # 2. Tratamento para "O que você pode fazer?"
    ajuda_keywords = ['o que você faz', 'o que voce faz', 'o que você pode fazer', 'o que voce pode fazer', 'como pode me ajudar', 'ajuda']
    if any(keyword in pergunta_lower for keyword in ajuda_keywords):
        if sistema == 'facilite':
            return (
                "Eu sou o especialista em suporte do **Facilite ERP**! Posso te ajudar a:\n\n"
                "* Tirar dúvidas sobre Faturamento e Configuração Fiscal (NFC-e/NF-e).\n"
                "* Resolver erros de validação e regras de negócio do sistema.\n"
                "* Guiar você nos procedimentos operacionais do dia a dia.\n\n"
                "Como posso ser útil agora?"
            )
        else:
            return (
                "Eu sou o especialista em suporte do **Inpera ERP**! Estou aqui para:\n\n"
                "* Auxiliar no treinamento e introdução ao sistema.\n"
                "* Consultar histórico de auditorias e boas práticas.\n"
                "* Responder dúvidas sobre a base de conhecimento e parametrizações.\n\n"
                "O que você deseja consultar hoje?"
            )

    # 3. Fluxo Normal de Chamada do Gemini
    try:
        # Configura a chave de API do Gemini
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Junta o contexto extraído do Notion (se houver) para passar à IA
        contexto_notion = "\n".join([c.get('texto', '') for c in chunks]) if chunks else ""
        
        # System Prompt dinâmico instruindo o comportamento para dados ausentes
        system_prompt = (
            f"Você é o especialista de suporte técnico do ecossistema {sistema.upper()} ERP.\n"
            f"Utilize o seguinte contexto extraído do Notion para responder ao usuário:\n{contexto_notion}\n\n"
            "DIRETRIZ CRÍTICA: Se a resposta para a dúvida do usuário NÃO estiver explicitamente descrita no "
            "contexto fornecido acima, você NÃO deve inventar procedimentos. Em vez disso, responda estritamente "
            "informando que não localizou esse procedimento exato na base de dados atual, solicite que o usuário "
            "forneça mais detalhes ou o código do erro, e tente sugerir de forma amigável qual módulo ou tela "
            "do sistema provavelmente está relacionado ao problema (ex: Faturamento, Cadastro de Clientes, Banco de Dados, etc)."
        )
        
        resposta = model.generate_content([system_prompt, pergunta])
        return resposta.text
        
    except Exception as e:
        logger.error(f"Erro ao chamar a API do Gemini: {e}")
        return "Desculpe, ocorreu um erro ao gerar a resposta com a IA. Por favor, tente novamente em alguns instantes."