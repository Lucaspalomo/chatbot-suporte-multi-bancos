from langchain_core.documents import Document
import sqlite3
import os
from typing import List

# Descobre o caminho dos bancos com base na estrutura de pastas que criamos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FACILITE = os.path.join(BASE_DIR, 'facilite', 'banco', 'facilite_auditoria.db')
DB_INPERA = os.path.join(BASE_DIR, 'inpera', 'banco', 'inpera_auditoria.db')

def buscar_solucoes_historicas(pergunta: str, sistema: str) -> str:
    """
    Busca no SQLite conversas passadas sobre o mesmo erro para servir de aprendizado.
    """
    # Escolhe o banco correto dependendo do sistema
    db_path = DB_FACILITE if sistema == 'facilite' else DB_INPERA
    
    if not os.path.exists(db_path):
        return ""
        
    try:
        # Extrai palavras-chave simples da pergunta (ex: 'BDE', 'PDV', 'Erro')
        palavras = [p for p in pergunta.split() if len(p) > 3]
        if not palavras:
            return ""
            
        # Monta um filtro SQL dinâmico usando LIKE para cada palavra relevante
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


# ===========================================================================
# ATUALIZAÇÃO DA SUA FUNÇÃO DE RESPOSTA
# ===========================================================================
# Adicione o parâmetro 'sistema' na assinatura da função lá no seu app_rag.py
def responder_ticket_suporte(pergunta: str, blocos: List[Document], sistema: str = 'facilite') -> str:
    
    # 1. Resgata o contexto estático do Notion
    contexto_notion = "\n\n---\n\n".join([b.page_content for b in blocos]) if blocos else "NENHUM PROCEDIMENTO ENCONTRADO NO NOTION."
    
    # 2. Resgata a memória viva do banco SQLite de conversas passadas!
    memoria_historica = buscar_solucoes_historicas(pergunta, sistema)

    system_prompt = (
        "Você é um Engenheiro de Suporte ERP Sênior especialista em resolver problemas técnicos.\n"
        "Diretrizes de Resposta e Comportamento:\n"
        "1. Foco Prático Absoluto: Vá direto ao ponto. Traga apenas o passo a passo (procedimento prático) para resolver o problema.\n"
        "2. Formatação em Negrito: Sempre que mencionar nomes de ferramentas, utilitários, aplicativos, rotinas, caminhos de pastas, menus, parâmetros, campos ou **botões**, coloque o termo estritamente em **negrito**.\n"
        "3. Estilo Visual: Formate a sua resposta usando tópicos ou listas numeradas.\n\n"
        "REGRA DE APRENDIZADO E CRUZAMENTO DE DADOS:\n"
        "- Abaixo você receberá o 'CONTEXTO DO NOTION' (manual oficial) e a 'MEMÓRIA DE CONVERSAS ANTERIORES' (histórico real do suporte).\n"
        "- Se na 'MEMÓRIA DE CONVERSAS ANTERIORES' houver um registro de que um usuário resolveu o problema por um caminho diferente, mais rápido ou alternativo (ex: o manual dizia XYZ mas na prática deu certo por XYA), VOCÊ DEVE ADOTAR E PRIORIZAR A SOLUÇÃO QUE DEU CERTO NA PRÁTICA.\n"
        "- Responda de forma natural, fundindo o conhecimento se necessário, como: 'Eu já vi esse cenário acontecer antes, siga este procedimento...'\n\n"
        f"CONTEXTO DO NOTION EXTENSO:\n{contexto_notion}\n"
        f"{memoria_historica}"
    )
    
    # Aqui segue a sua chamada normal do Gemini (gemini-2.5-flash) enviando o system_prompt...