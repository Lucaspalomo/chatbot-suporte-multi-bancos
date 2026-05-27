import os
import logging
from flask import Flask, render_template, request, jsonify
from app_rag import (
    buscar_dados_base_conhecimento, 
    preparar_documentos_rag, 
    criar_banco_vetores_local, 
    buscar_blocos_semanticos, 
    responder_ticket_suporte
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Bancos vetoriais separados fisicamente na memória
BANCO_FACILITE = None
BANCO_INPERA = None

# IDs das bases que extraímos do seu Notion
NOTION_DATABASE_INPERA = "36b1e757f06480d5b493d95f96e94931"
NOTION_DATABASE_FACILITE = "36d1e757f064805bbea0f96c9fc6432f"

# ===========================================================================
# ROTAS DO PORTAL FACILITE (Aba / Rota 1)
# ===========================================================================
@app.route('/facilite')
def home_facilite():
    cursos_facilite = [
        {"titulo": "Dominando o ERP Facilite", "categoria": "Faturamento", "imagem": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=500", "duracao": "12h"},
        {"titulo": "Configuração Fiscal Avançada (NFC-e/NF-e)", "categoria": "Fiscal", "imagem": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=500", "duracao": "8h"}
    ]
    return render_template('facilite.html', cursos=cursos_facilite)

@app.route('/perguntar_facilite', methods=['POST'])
def perguntar_facilite():
    global BANCO_FACILITE
    if BANCO_FACILITE is None:
        return jsonify({"resposta": "A base Facilite está inicializando. Aguarde."}), 503
        
    dados = request.get_json()
    pergunta = dados.get('pergunta', '')
    
    # Busca e responde olhando APENAS para a base do Facilite
    chunks = buscar_blocos_semanticos(pergunta, BANCO_FACILITE)
    resposta_ia = responder_ticket_suporte(pergunta, chunks)
    return jsonify({"resposta": resposta_ia})


# ===========================================================================
# ROTAS DO PORTAL INPERA (Aba / Rota 2)
# ===========================================================================
@app.route('/inpera')
def home_inpera():
    cursos_inpera = [
        {"titulo": "Introdução ao Sistema Inpera", "categoria": "Treinamento", "imagem": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=500", "duracao": "6h"},
        {"titulo": "Gerenciamento de Banco Firebird no Inpera", "categoria": "Banco de Dados", "imagem": "https://images.unsplash.com/photo-1544383835-bda2bc66a55d?w=500", "duracao": "10h"}
    ]
    return render_template('inpera.html', cursos=cursos_inpera)

@app.route('/perguntar_inpera', methods=['POST'])
def perguntar_inpera():
    global BANCO_INPERA
    if BANCO_INPERA is None:
        return jsonify({"resposta": "A base Inpera está inicializando. Aguarde."}), 503
        
    dados = request.get_json()
    pergunta = dados.get('pergunta', '')
    
    # Busca e responde olhando APENAS para a base do Inpera
    chunks = buscar_blocos_semanticos(pergunta, BANCO_INPERA)
    resposta_ia = responder_ticket_suporte(pergunta, chunks)
    return jsonify({"resposta": resposta_ia})


# ===========================================================================
# INICIALIZAÇÃO PARALELA DAS BASES DE DADOS
# ===========================================================================
if __name__ == '__main__':
    print("\n============================================================")
    print("CARREGANDO E SEPARANDO AS BASES DO NOTION (FACILITE & INPERA)")
    print("============================================================\n")
    
    import app_rag  # Garante o acesso direto ao escopo do outro arquivo
    
    # Carga isolada do Facilite
    try:
        print("[1/2] Carregando dados do Facilite...")
        # Injetamos dinamicamente o ID do Facilite na variável que a função espera
        app_rag.NOTION_DATABASE_ID = NOTION_DATABASE_FACILITE
        
        dados_f = app_rag.buscar_dados_base_conhecimento() 
        docs_f = app_rag.preparar_documentos_rag(dados_f)
        BANCO_FACILITE = app_rag.criar_banco_vetores_local(docs_f)
        print("[OK] Base Facilite Montada com sucesso.")
    except Exception as e:
        print(f"[ERRO FACILITE]: {e}")
        
    # Carga isolada do Inpera
    try:
        print("\n[2/2] Carregando dados do Inpera...")
        # Injetamos dinamicamente o ID do Inpera na variável que a função espera
        app_rag.NOTION_DATABASE_ID = NOTION_DATABASE_INPERA
        
        dados_i = app_rag.buscar_dados_base_conhecimento()
        docs_i = app_rag.preparar_documentos_rag(dados_i)
        BANCO_INPERA = app_rag.criar_banco_vetores_local(docs_i)
        print("[OK] Base Inpera Montada com sucesso.")
    except Exception as e:
        print(f"[ERRO INPERA]: {e}")

    print("\n============================================================")
    print("   TODOS OS BANCOS LOCALIZADOS - SERVIDOR WEB ATIVO")
    print("============================================================\n")

    app.run(debug=True, port=5000)