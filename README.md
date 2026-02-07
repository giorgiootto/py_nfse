# 🤖 Agente NFSe - API TecnoSpeed

Cliente Python para automatizar consulta e download de Notas Fiscais de Serviço Eletrônicas (NFSe) usando a API de Notas Tomadas da TecnoSpeed.

## 📋 Funcionalidades

- ✅ Consultar cidades homologadas
- ✅ Cadastrar certificado digital (.pfx)
- ✅ Adicionar consultas de notas tomadas
- ✅ Consultar status de protocolos
- ✅ Download automático de XMLs das notas
- ✅ Processo completo automatizado (adicionar + aguardar + baixar)
- ✅ Suporte a paginação (mais de 100 notas)

## 🚀 Como Usar

### 1. Pré-requisitos

- Python 3.12+
- Conta no TecnoAccount (https://conta.tecnospeed.com.br/)
- Token de acesso (obtido no TecnoAccount)
- Certificado digital (.pfx) do tomador

### 2. Instalar Dependências

```bash
uv pip install requests python-dotenv
```

Ou:

```bash
uv pip install -e .
```

### 3. Executar

```bash
python main.py
```

Ou com uv:

```bash
uv run main.py
```

## 📖 Guia de Uso

### Menu Interativo

O programa apresenta um menu com as seguintes opções:

1. **Consultar cidades homologadas** - Lista todas as cidades disponíveis na API
2. **Cadastrar certificado** - Faz upload do certificado .pfx
3. **Adicionar consulta de notas** - Cria uma consulta para período específico
4. **Consultar protocolo** - Verifica status de uma consulta
5. **Processo completo** - Executa tudo automaticamente

### Processo Completo (Recomendado)

A opção 5 do menu executa todo o fluxo:

1. Adiciona a consulta de notas
2. Aguarda o processamento (pode levar até 1 hora)
3. Baixa todos os XMLs automaticamente
4. Salva no diretório `./downloads`

### Exemplo de Uso

```python
from main import TecnoSpeedNFSeAPI

# Criar cliente
api = TecnoSpeedNFSeAPI(
    token_sh="seu_token_aqui",
    cpf_cnpj_software_house="12345678000199",
    cpf_cnpj_tomador="98765432000188"
)

# Consultar cidades
cidades = api.consultar_cidades_homologadas("CURITIBA")

# Processo completo
api.processar_consulta_completa(
    codigo_cidade="4106902",  # Curitiba
    prestador_cnpj="12345678000199",
    periodo_dias=30
)
```

## 🔧 Configuração

### Via Arquivo .env (Opcional)

Crie um arquivo `.env` baseado no `.env.example`:

```env
TOKEN_SH=c84d2f944b9f695eb65c10c7b7a1da8b
CPF_CNPJ_SOFTWARE_HOUSE=12345678000199
CPF_CNPJ_TOMADOR=98765432000188
DOWNLOAD_DIR=./downloads
```

## 📦 Estrutura do Projeto

```
py_nfse/
├── main.py              # Cliente da API TecnoSpeed
├── pyproject.toml       # Configuração e dependências
├── .env.example         # Exemplo de configuração
├── .gitignore          # Arquivos ignorados pelo Git
├── README.md           # Este arquivo
└── downloads/          # Diretório padrão dos XMLs
```

## � Notas Importantes
### 🎯 Entendendo PRESTADOR vs TOMADOR

**É muito importante entender esses conceitos!**

| Termo | Quem é? | O que significa? |
|-------|---------|------------------|
| **PRESTADOR** | Quem **EMITIU** as notas | A empresa que prestou serviços **PARA VOCÊ** |
| **TOMADOR/DESTINATÁRIO** | **VOCÊ** | A empresa que **RECEBEU/TOMOU** os serviços |

**Exemplo prático:**
- Você contratou uma empresa de consultoria (CNPJ 12.345.678/0001-99)
- Essa empresa emitiu uma NFSe contra o seu CNPJ (98.765.432/0001-88)
- Na consulta:
  - **Prestador** = 12.345.678/0001-99 (quem prestou o serviço)
  - **Tomador** = 98.765.432/0001-88 (VOCÊ, quem tomou o serviço)

### 📋 Campos da API

```json
{
  "prestador": {
    "cpfCnpj": "12345678000199",           // ← Quem EMITIU a nota
    "inscricaoMunicipal": "12345"          // ← IM de quem EMITIU
  },
  "destinatario": {
    "cpfCnpj": "98765432000188",           // ← VOCÊ (tomador)
    "inscricaoMunicipal": "98765"          // ← SUA inscrição municipal ⚠️
  }
}
```

**⚠️ ATENÇÃO**: `destinatario.inscricaoMunicipal` é a **SUA** Inscrição Municipal (do TOMADOR)!
### ⚠️ CNPJ do Prestador - Obrigatório ou Não?

**A exigência do CNPJ do prestador VARIA POR MUNICÍPIO!**

- ✅ **Alguns municípios exigem** o CNPJ do prestador
- ✅ **Outros municípios NÃO exigem**
- ✅ Use a opção 1 do menu para ver quais municípios exigem (ícone 🏢)
- ✅ Ou use `obter_requisitos_cidade(codigo_ibge)` para verificar

```python
# Verificar requisitos de uma cidade
requisitos = api.obter_requisitos_cidade("4106902")  # Curitiba
print(f"Prestador obrigatório: {requisitos['prestador_obrigatorio']}")
```

### 📊 Campos Obrigatórios por Município

Cada município pode ter requisitos diferentes:
- 🏢 **Prestador obrigatório**: CPF/CNPJ do prestador é necessário
- 🔐 **Certificado obrigatório**: Precisa cadastrar certificado digital
- 👤 **Login obrigatório**: Precisa fornecer login do município  
- 🔑 **Senha obrigatória**: Precisa fornecer senha do município

## �🔐 Segurança

⚠️ **IMPORTANTE**: 
- **NUNCA** commite tokens ou certificados no Git
- **NUNCA** compartilhe suas credenciais
- Use o arquivo `.env` para configurações sensíveis (já incluído no .gitignore)
- Mantenha seus certificados em local seguro

## 📚 Documentação da API

Este projeto implementa os seguintes passos da API TecnoSpeed:

- **Passo 3**: Consultar cidades homologadas
- **Passo 4**: Adicionar uma consulta de notas
- **Passo 5**: Consultar status do protocolo
- **Passo 6**: Consultar e baixar notas pelo protocolo

Documentação completa: https://atendimento.tecnospeed.com.br/hc/pt-br/articles/360047695974

## 📝 Fluxo da API

```
1. Consultar cidades homologadas
   ↓
2. Cadastrar certificado (uma vez)
   ↓
3. Adicionar consulta de notas
   ↓
4. Aguardar processamento (30s - 1h+)
   ↓
5. Consultar protocolo (verificar se CONCLUÍDO)
   ↓
6. Baixar XMLs das notas
```

## ⏱️ Tempo de Processamento

- **Mínimo**: 30 segundos
- **Recomendado**: Aguardar 1 hora antes de consultar
- **Variável**: Depende do município e quantidade de notas

## 🐛 Troubleshooting

### Erro 401 (Não autorizado)
- Verifique se o token está correto
- Confirme CPF/CNPJ da Software House
- Confirme CPF/CNPJ do Tomador

### Erro 404 (Não encontrado)
- Verifique se o código IBGE está correto
- Use a opção 1 do menu para consultar cidades válidas

### Protocolo em PROCESSANDO
- É normal! Aguarde mais tempo
- Pode levar até 1 hora ou mais
- Consulte novamente depois

### Erro ao cadastrar certificado
- Verifique se o arquivo .pfx existe
- Confirme se a senha está correta
- Certifique-se de que o certificado está válido

## 🤝 Contribuições

Sugestões e melhorias são bem-vindas!

## 📄 Licença

Este projeto é fornecido como está, para fins educacionais e de automação.
