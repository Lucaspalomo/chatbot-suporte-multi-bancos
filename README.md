# 🤖 Sistema RAG Multi-Bancos (Facilite & Inpera)

Este projeto é um assistente de suporte inteligente baseado em IA que utiliza a técnica de **RAG (Retrieval-Augmented Generation)**. Ele se conecta a bases de conhecimento do Notion de forma isolada, permitindo que a equipe de suporte consulte procedimentos operacionais e ocorrências técnicas (OT) dos sistemas Facilite e Inpera de maneira totalmente independente, sem cruzamento de dados.

## 🛠️ Tecnologias Utilizadas
- **Back-end:** Python 3 + Flask
- **Banco de Dados Vetorial:** ChromaDB (Local e isolado em memória RAM)
- **Modelo de Linguagem (LLM):** Gemini 2.5 Flash (via SDK `google-genai`)
- **Orquestrador:** LangChain

## 📁 Estrutura do Projeto
```text
├── app_rag.py           # Core do RAG (Conexão Notion, IA e Busca Semântica)
├── web_app.py           # Servidor Flask e gerenciamento de rotas
├── requirements.txt     # Dependências para deploy na nuvem
├── README.md            # Documentação do repositório
└── templates/           # Interfaces Visuais (Front-end)
    ├── facilite.html    # Portal Facilite Flix (Tema Vermelho)
    └── inpera.html      # Portal Inpera Play (Tema Azul)