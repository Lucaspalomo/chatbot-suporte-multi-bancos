import os
import logging
import sqlite3
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

# Configura o Flask para enxergar múltiplos caminhos de templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=[
    os.path.join(BASE_DIR, 'facilite', 'templates'),
    os.path.join(BASE_DIR, 'inpera', 'templates')
])

# Caminhos isolados para cada banco de dados de auditoria
DB_FACILITE = os.path.join(BASE_DIR, 'facilite', 'banco', 'facilite_auditoria.db')
DB_INPERA = os.path.join(BASE_DIR, 'inpera', 'banco', 'inpera_auditoria.db')

# ===========================================================================
# CAMADA DE BANCO DE DADOS ISOLADA
# ===========================================================================
def inicializar_bancos_dados():
    """Garante que as pastas de banco existam e cria as tabelas isoladas."""
    for db_path in [DB_FACILITE, DB_INPERA]:
        # Cria a pasta 'banco' correspondente se não existir
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_consultas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario VARCHAR(50) NOT NULL,
                pergunta TEXT NOT NULL,
                resposta TEXT,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    print("[OK] Bancos de dados Facilite e Inpera inicializados nas suas respectivas pastas.")

def salvar_log(db_path, usuario, pergunta, resposta):
    """Grava o log no banco de dados especificado."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO log_consultas (usuario, pergunta, resposta) VALUES (?, ?, ?)
        ''', (usuario, pergunta, resposta))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Falha ao salvar log de auditoria: {e}")

# Bancos vetoriais separados em memória
BANCO_FACILITE = None
BANCO_INPERA = None

NOTION_DATABASE_INPERA = "36b1e757f06480d5b493d95f96e94931"
NOTION_DATABASE_FACILITE = "36d1e757f064805bbea0f96c9fc6432f"


# ===========================================================================
# ROTAS DO PORTAL FACILITE
# ===========================================================================
@app.route('/facilite')
def home_facilite():
    # Aqui você poderá expandir sua lista de treinamentos à vontade!
    cursos_facilite = [
        {"titulo": "Dominando o ERP Facilite", "categoria": "Faturamento", "imagem": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=500", "duracao": "12h"},
        {"titulo": "Configuração Fiscal Avançada (NFC-e/NF-e)", "categoria": "Fiscal", "imagem": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=500", "duracao": "8h"}
    ]
    return render_template('facilite.html', Header_Sistema="Facilite", cursos_facilite=cursos_facilite)

@app.route('/perguntar_facilite', methods=['POST'])
def perguntar_facilite():
    global BANCO_FACILITE
    if BANCO_FACILITE is None:
        return jsonify({"resposta": "A base Facilite está inicializando..."}), 503
        
    dados = request.get_json()
    pergunta = dados.get('pergunta', '')
    usuario_atual = dados.get('usuario', 'operador.facilite')
    
    chunks = buscar_blocos_semanticos(pergunta, BANCO_FACILITE)
    resposta_ia = responder_ticket_suporte(pergunta, chunks, sistema='facilite')
    
    # Salva no banco de dados exclusivo do Facilite
    salvar_log(DB_FACILITE, usuario_atual, pergunta, resposta_ia)
    return jsonify({"resposta": resposta_ia})


# ===========================================================================
# ROTAS DO PORTAL INPERA
# ===========================================================================
@app.route('/inpera')
def home_inpera():
    # Removido o curso fictício de Firebird que gerava confusão
    cursos_inpera = [
        {"titulo": "Introdução ao Sistema Inpera", "categoria": "Treinamento", "imagem": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=500", "duracao": "6h"}
    ]
    return render_template('inpera.html', Header_Sistema="Inpera", cursos_inpera=cursos_inpera)

@app.route('/perguntar_inpera', methods=['POST'])
def perguntar_inpera():
    global BANCO_INPERA
    if BANCO_INPERA is None:
        return jsonify({"resposta": "A base Inpera está inicializando..."}), 503
        
    dados = request.get_json()
    pergunta = dados.get('pergunta', '')
    usuario_atual = dados.get('usuario', 'operador.inpera')
    
    chunks = buscar_blocos_semanticos(pergunta, BANCO_INPERA)
    resposta_ia = responder_ticket_suporte(pergunta, chunks, sistema='inpera')
    
    # Salva no banco de dados exclusivo do Inpera
    salvar_log(DB_INPERA, usuario_atual, pergunta, resposta_ia)
    return jsonify({"resposta": resposta_ia})


# ===========================================================================
# INICIALIZAÇÃO
# ===========================================================================
if __name__ == '__main__':
    inicializar_bancos_dados()
    import app_rag  
    
    # Carga Facilite
    try:
        print("[1/2] Carregando dados do Facilite...")
        app_rag.NOTION_DATABASE_ID = NOTION_DATABASE_FACILITE
        dados_f = app_rag.buscar_dados_base_conhecimento() 
        docs_f = app_rag.preparar_documentos_rag(dados_f)
        BANCO_FACILITE = app_rag.criar_banco_vetores_local(docs_f)
    except Exception as e:
        print(f"[ERRO FACILITE]: {e}")
        
    # Carga Inpera
    try:
        print("\n[2/2] Carregando dados do Inpera...")
        app_rag.NOTION_DATABASE_ID = NOTION_DATABASE_INPERA
        dados_i = app_rag.buscar_dados_base_conhecimento()
        docs_i = app_rag.preparar_documentos_rag(dados_i)
        BANCO_INPERA = app_rag.criar_banco_vetores_local(docs_i)
    except Exception as e:
        print(f"[ERRO INPERA]: {e}")

    app.run(debug=True, port=5000)