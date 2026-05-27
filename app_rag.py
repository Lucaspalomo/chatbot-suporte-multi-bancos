import os
import logging
from typing import List, Dict, Any
import requests
from dotenv import load_dotenv  # 1. ADICIONE ESSA LINHA AQUI

# Componentes do LangChain para processamento e divisão de texto
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# Nova biblioteca oficial padrão do Google GenAI para a Resposta Final
from google import genai
from google.genai import types

# Ativa a leitura do arquivo .env (deve rodar antes de carregar as variáveis)
load_dotenv()  # 2. ADICIONE ESSA LINHA AQUI

# Configuração de Logs para monitoramento no terminal
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===========================================================================
# 1. CONFIGURAÇÃO E VARIÁVEIS DE AMBIENTE (MASCARADAS)
# ===========================================================================
# 3. MODIFIQUE AS DUAS LINHAS ABAIXO TIRANDO O TEXTO REAL E ADICIONANDO O GETENV:
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# DECLARE ESTA LINHA ABAIXO (Valor padrão que será substituído pelo web_app)
NOTION_DATABASE_ID = "" 

# Inicializa o novo cliente oficial do Google GenAI
client = genai.Client(api_key=GOOGLE_API_KEY)


# ===========================================================================
# 2. CONEXÃO COM A BASE DE DADOS REAL DO NOTION
# ===========================================================================
def buscar_conteudo_da_pagina(page_id: str) -> str:
    url = f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=100"
    headers = {"Authorization": f"Bearer {NOTION_API_KEY}", "Notion-Version": "2022-06-28"}
    try:
        resposta = requests.get(url, headers=headers)
        if resposta.status_code == 200:
            blocos = resposta.json().get("results", [])
            texto_pagina = []
            for bloco in blocos:
                tipo = bloco.get("type", "")
                if tipo in ["paragraph", "heading_1", "heading_2", "heading_3", "numbered_list_item", "bulleted_list_item"]:
                    conteudo_bloco = bloco.get(tipo, {}).get("rich_text", [])
                    if conteudo_bloco:
                        texto_pagina.append(conteudo_bloco[0].get("plain_text", ""))
            return "\n".join(texto_pagina)
    except Exception as e:
        logger.warning(f"Não foi possível ler o corpo da página {page_id}: {e}")
    return ""

def buscar_dados_base_conhecimento() -> List[Dict[str, Any]]:
    logger.info("Conectando à API do Notion para buscar registros reais...")
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    try:
        resposta = requests.post(url, headers=headers)
        resposta.raise_for_status()
        dados_notion = resposta.json()
        resultados_finais = []
        for linha in dados_notion.get("results", []):
            page_id = linha.get("id", "")
            propriedades = linha.get("properties", {})
            
            def obter_texto_notion(nome_coluna: str) -> str:
                coluna = propriedades.get(nome_coluna, {})
                if not coluna: return ""
                tipo = coluna.get("type", "")
                if tipo == "title" and coluna.get("title"):
                    return coluna["title"][0].get("plain_text", "")
                elif tipo == "rich_text" and coluna.get("rich_text"):
                    return coluna["rich_text"][0].get("plain_text", "")
                elif tipo == "select" and coluna.get("select"):
                    return coluna["select"].get("name", "")
                elif tipo == "multi_select" and coluna.get("multi_select"):
                    return ", ".join([item.get("name", "") for item in coluna["multi_select"]])
                elif tipo == "url" and coluna.get("url"):
                    return coluna.get("url", "")
                return ""

            corpo_real_notion = buscar_conteudo_da_pagina(page_id)
            registro_formatado = {
                "Nome": obter_texto_notion("Nome"),
                "Categoria": obter_texto_notion("Categoria"),
                "Erros Comuns (Tags)": obter_texto_notion("Erros Comuns (Tags)"),
                "Link Relacionado": obter_texto_notion("Link Relacionado"),
                "Módulo": obter_texto_notion("Módulo"),
                "Resumo para IA": obter_texto_notion("Resumo para IA"),
                "Tags": obter_texto_notion("Tags"),
                "Corpo_Pagina": corpo_real_notion  
            }
            if registro_formatado["Nome"]:
                resultados_finais.append(registro_formatado)
        logger.info(f"Sucesso! {len(resultados_finais)} registros reais importados do Notion.")
        return resultados_finais
    except Exception as e:
        logger.error(f"Erro ao obter dados do Notion: {str(e)}")
        raise e

def preparar_documentos_rag(dados: List[Dict[str, Any]]) -> List[Document]:
    documentos_finais = []
    for linha in dados:
        texto_completo = (
            f"DOCUMENTO TÉCNICO ERP: {linha['Nome']}\n"
            f"MODULO DO SISTEMA: {linha['Módulo']} | CATEGORIA: {linha['Categoria']}\n"
            f"ASSUNTOS E TAGS: {linha['Tags']} certificado digital a1 pfx instalar configuracao\n"
            f"RESUMO OPERACIONAL: {linha['Resumo para IA']}\n"
            f"ERROS DO SISTEMA: {linha['Erros Comuns (Tags)']}\n\n"
            f"MANUAL COMPLETO PROCEDIMENTO:\n{linha['Corpo_Pagina']}"
        )
        metadados = {"titulo": linha["Nome"], "modulo": linha["Módulo"]}
        doc = Document(page_content=texto_completo, metadata=metadados)
        documentos_finais.append(doc)
    return documentos_finais


# ===========================================================================
# 3. CHUNKING E VETORIZAÇÃO LOCAL AUTOMÁTICA (MUITO MAIS RÁPIDO)
# ===========================================================================
def criar_banco_vetores_local(documentos: List[Document]) -> Chroma:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200, chunk_overlap=120, separators=["\n### ", "\n\n", "\n", " ", ""]
    )
    blocos_texto = text_splitter.split_documents(documentos)
    
    # O ChromaDB usa por padrão o modelo local 'all-MiniLM-L6-v2' se não passarmos nada.
    # Ele é perfeito para lidar com erros de digitação e sinônimos de forma 100% offline.
    return Chroma.from_documents(documents=blocos_texto, embedding=None)


# ===========================================================================
# 4. BUSCA SEMÂNTICA LOCAL E TRATAMENTO DA IA
# ===========================================================================
def buscar_blocos_semanticos(pergunta: str, banco_vetores: Chroma) -> List[Document]:
    return banco_vetores.similarity_search(pergunta, k=4)

def responder_ticket_suporte(pergunta: str, blocos: List[Document]) -> str:
    if not blocos:
        return "Não encontrei esse procedimento exato na base de dados."

    contexto_unificado = "\n\n---\n\n".join([b.page_content for b in blocos])
    
    system_prompt = (
        "Você é um Engenheiro de Suporte ERP Sênior especialista em resolver problemas técnicos do sistema Facilite e Inpera.\n"
        "Instruções Estritas de Resposta:\n"
        "1. Baseie-se UNICAMENTE nas informações passadas no 'CONTEXTO' abaixo. Se a solução não estiver lá de forma clara, responda exatamente: 'Não encontrei esse procedimento exato na base de dados'.\n"
        "2. Formate sua resposta exclusivamente usando tópicos numerados.\n"
        "3. Realce caminhos de sistema, nomes de telas, parâmetros e **botões** in negrito.\n\n"
        f"CONTEXTO DE SUPORTE EXTRAÍDO:\n{contexto_unificado}"
    )

    try:
        resposta = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Dúvida do Usuário: {pergunta}",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0
            )
        )
        return resposta.text
    except Exception as e:
        logger.error(f"Falha na API Gemini do Google: {str(e)}")
        return "Erro ao processar requisição no modelo analítico do Gemini."


# ===========================================================================
# EXECUÇÃO DO FLUXO COMPLETO
# ===========================================================================
if __name__ == "__main__":
    print("\n============================================================")
    print("INICIALIZANDO MOTOR RAG SEGURO COM EMBEDDINGS LOCAIS NATIVOS")
    print("============================================================\n")
    
    try:
        dados_reais = buscar_dados_base_conhecimento()
        if not dados_reais:
            print("[AVISO] A tabela do Notion retornou vazia.")
        else:
            docs_preparados = preparar_documentos_rag(dados_reais)
            banco_indexado = criar_banco_vetores_local(docs_preparados)
            print("\n[OK] Dados do Notion indexados com sucesso localmente.")
            print("Digite 'sair' a qualquer momento para encerrar o programa.\n")
            
            # -----------------------------------------------------------------
            # LOOP DE PERGUNTAS NO TERMINAL
            # -----------------------------------------------------------------
            while True:
                print("-" * 60)
                pergunta_teste = input("Digite a dúvida do cliente (ou 'sair'): ")
                
                # Condição de parada
                if pergunta_teste.strip().lower() == 'sair':
                    print("\nEncerrando o assistente de suporte. Até mais!")
                    break
                
                # Valida se o usuário não apertou enter sem digitar nada
                if not pergunta_teste.strip():
                    print("[Aviso] Por favor, digite uma pergunta válida.")
                    continue
                
                print(f"\n-> Consultando a IA sobre: '{pergunta_teste}'...")
                
                chunks = buscar_blocos_semanticos(pergunta_teste, banco_indexado)
                resposta = responder_ticket_suporte(pergunta_teste, chunks)
                
                print("\nResposta Final do Gemini (Baseado no seu Notion):")
                print(resposta)
                print("\n")
                
    except Exception as error:
        print(f"\n[ERRO NO FLUXO]: Ocorreu um problema na execução. {error}")
    print("\n============================================================")