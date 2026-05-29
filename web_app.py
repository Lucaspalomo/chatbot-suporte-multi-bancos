import os
import logging
import sqlite3
import jinja2  # <--- Adicionado para resolver o ChoiceLoader dos templates
from flask import Flask, render_template, request, jsonify, redirect
from dotenv import load_dotenv

# Carrega o arquivo .env primeiro
load_dotenv()

# Importa o motor do RAG do arquivo app_rag.py
import app_rag
from app_rag import (
    buscar_dados_base_conhecimento, 
    preparar_documentos_rag, 
    criar_banco_vetores_local, 
    buscar_blocos_semanticos, 
    responder_ticket_suporte
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# CORREÇÃO DEFINITIVA DO FLASK (template_folder como string única)
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder=".")

# Configura o Jinja para buscar os templates dinamicamente dentro de cada sistema
app.jinja_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader(os.path.join(BASE_DIR, 'facilite', 'templates')),
    jinja2.FileSystemLoader(os.path.join(BASE_DIR, 'inpera', 'templates'))
])

# Garante que o Token do arquivo .env seja enviado para o motor do RAG
app_rag.NOTION_TOKEN = os.getenv("NOTION_TOKEN")

# Caminhos isolados para cada banco de dados de auditoria e credenciais
DB_FACILITE = os.path.join(BASE_DIR, 'facilite', 'banco', 'facilite_auditoria.db')
DB_INPERA = os.path.join(BASE_DIR, 'inpera', 'banco', 'inpera_auditoria.db')


# ===========================================================================
# CAMADA DE BANCO DE DADOS ISOLADA
# ===========================================================================
def inicializar_bancos_dados():
    """Garante que as pastas de banco existam e cria as tabelas isoladas."""
    for db_path in [DB_FACILITE, DB_INPERA]:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Tabela de logs existente
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_consultas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario VARCHAR(50) NOT NULL,
                pergunta TEXT NOT NULL,
                resposta TEXT,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # NOVA TABELA: Cadastro de Usuários do Ecossistema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(100) NOT NULL,
                documento VARCHAR(20) NOT NULL,
                vinculo VARCHAR(20) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                senha VARCHAR(100) NOT NULL,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    print("[OK] Bancos de dados Facilite e Inpera inicializados (Tabelas: log_consultas e usuarios).")

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

def cadastrar_novo_usuario(db_path, nome, documento, vinculo, email, senha):
    """Insere um novo usuário na tabela correspondente ao ecossistema."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO usuarios (nome, documento, vinculo, email, senha) 
            VALUES (?, ?, ?, ?, ?)
        ''', (nome, documento, vinculo, email, senha))
        conn.commit()
        conn.close()
        return True, "Cadastro realizado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "Erro: Este e-mail já está cadastrado em nossa base."
    except Exception as e:
        logger.error(f"Falha ao cadastrar usuário: {e}")
        return False, f"Erro interno do servidor: {e}"


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
    
    salvar_log(DB_FACILITE, usuario_atual, pergunta, resposta_ia)
    return jsonify({"resposta": resposta_ia})

# --- NOVAS ROTAS DE CADASTRO FACILITE ---
@app.route('/facilite/cadastro', methods=['GET', 'POST'])
def cadastro_facilite():
    mensagem = None
    sucesso = False
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        documento = request.form.get('documento')
        vinculo = request.form.get('vinculo')
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        sucesso, mensagem = cadastrar_novo_usuario(DB_FACILITE, nome, documento, vinculo, email, senha)
        
    # Como seu ChoiceLoader mapeia a pasta 'facilite/templates', basta chamar o arquivo direto
    return render_template('facilite_cadastro.html', mensagem=mensagem, sucesso=sucesso)


# ===========================================================================
# ROTAS DO PORTAL INPERA
# ===========================================================================
@app.route('/inpera')
def home_inpera():
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
    
    salvar_log(DB_INPERA, usuario_atual, pergunta, resposta_ia)
    return jsonify({"resposta": resposta_ia})

# --- NOVAS ROTAS DE CADASTRO INPERA ---
@app.route('/inpera/cadastro', methods=['GET', 'POST'])
def cadastro_inpera():
    mensagem = None
    sucesso = False
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        documento = request.form.get('documento')
        vinculo = request.form.get('vinculo')
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        sucesso, mensagem = cadastrar_novo_usuario(DB_INPERA, nome, documento, vinculo, email, senha)
        
    # Como seu ChoiceLoader mapeia a pasta 'inpera/templates', basta chamar o arquivo direto
    return render_template('inpera_cadastro.html', mensagem=mensagem, sucesso=sucesso)

# ===========================================================================
# SISTEMA DE AUTENTICAÇÃO CENTRALIZADO (MULTI-PORTAL)
# ===========================================================================

# ===========================================================================
# SISTEMA DE AUTENTICAÇÃO CENTRALIZADO (MULTI-PORTAL) - ATUALIZADO
# ===========================================================================

def verificar_credenciais(db_path, email, senha):
    """Verifica se o usuário existe e a senha coincide no banco informado."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT nome FROM usuarios WHERE email = ? AND senha = ?', (email, senha))
        usuario = cursor.fetchone()
        conn.close()
        return usuario is not None
    except Exception as e:
        logger.error(f"Erro ao verificar credenciais no banco {db_path}: {e}")
        return False

@app.route('/login', methods=['GET', 'POST'])
def login_centralizado():
    mensagem = None
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        # Checa se as credenciais batem em cada banco isolado
        tem_facilite = verificar_credenciais(DB_FACILITE, email, senha)
        tem_inpera = verificar_credenciais(DB_INPERA, email, senha)
        
        # CENÁRIO DUPLO: Existe nas duas bases. Direciona para a escolha.
        if tem_facilite and tem_inpera:
            return render_template('Escolha_contexto.html', email=email)
            
        # CENÁRIO EXCLUSIVO FACILITE: Direciona direto para o chatbot Facilite
        if tem_facilite:
            return redirect('/facilite')
            
        # CENÁRIO EXCLUSIVO INPERA: Direciona direto para o chatbot Inpera
        if tem_inpera:
            return redirect('/inpera')
            
        # NENHUM ENCONTRADO: Erro de autenticação
        mensagem = "E-mail ou senha incorretos. Por favor, tente novamente."
        
    return render_template('login.html', mensagem=mensagem)

# NOVA ROTA: Captura a escolha explícita do usuário na tela de múltiplos acessos
@app.route('/definir_contexto', methods=['POST'])
def definir_contexto():
    contexto = request.form.get('contexto') # Vai receber 'facilite' ou 'inpera'
    
    if contexto == 'facilite':
        return redirect('/facilite')
    elif contexto == 'inpera':
        return redirect('/inpera')
        
    return redirect('/login')

# ===========================================================================
# INICIALIZAÇÃO CONTRA MISTURA DE DADOS
# ===========================================================================
if __name__ == '__main__':
    inicializar_bancos_dados()
    
    # Carga Facilite
    try:
        print("[1/2] Carregando dados do Facilite...")
        app_rag.NOTION_DATABASE_ID = NOTION_DATABASE_FACILITE
        dados_f = app_rag.buscar_dados_base_conhecimento() 
        docs_f = app_rag.preparar_documentos_rag(dados_f)
        BANCO_FACILITE = app_rag.criar_banco_vetores_local(docs_f)
        print(f"[OK] Facilite carregado com {len(BANCO_FACILITE)} documentos.")
    except Exception as e:
        print(f"[ERRO FACILITE]: {e}")
        
    # Carga Inpera
    try:
        print("\n[2/2] Carregando dados do Inpera...")
        app_rag.NOTION_DATABASE_ID = NOTION_DATABASE_INPERA
        dados_i = app_rag.buscar_dados_base_conhecimento()
        docs_i = app_rag.preparar_documentos_rag(dados_i)
        BANCO_INPERA = app_rag.criar_banco_vetores_local(docs_i)
        print(f"[OK] Inpera carregado com {len(BANCO_INPERA)} documentos.")
    except Exception as e:
        print(f"[ERRO INPERA]: {e}")

    # RODAR COM use_reloader=False EVITA QUE O FLASK APAGUE AS VARIÁVEIS DA MEMÓRIA
    app.run(debug=True, port=5000, use_reloader=False, host="0.0.0.0")