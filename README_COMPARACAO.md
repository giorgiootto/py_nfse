# 🤖 Agente NFSe - Duas Abordagens

Este projeto oferece **duas formas** de automatizar o download de Notas Fiscais de Serviço Eletrônicas (NFSe):

## 📊 Comparação das Abordagens

| Característica | API TecnoSpeed | Playwright (Portal Gov) |
|----------------|----------------|-------------------------|
| **Arquivo** | `main.py` | `nfse_playwright_agent.py` |
| **Método** | API REST | Automação de Browser |
| **Certificado** | Upload do .pfx | Auto-seleção no Windows |
| **Interação Manual** | Nenhuma | Possível (1ª vez) |
| **Velocidade** | ⚡ Muito rápido | 🐢 Mais lento |
| **Confiabilidade** | ✅ Alta | ⚠️ Média (depende do site) |
| **Custo** | 💰 Pode ter custo | 🆓 Grátis |
| **Municípios** | Lista específica | Portal nacional |

## 🚀 Abordagem 1: API TecnoSpeed (Recomendada)

### ✅ Vantagens:
- Totalmente automatizada
- Rápida e confiável
- Suporta múltiplos municípios
- Sem captcha ou problemas de UI

### 📝 Como usar:

```bash
python main.py
```

**Menu:**
1. Consultar cidades homologadas
2. Cadastrar certificado
3. Listar certificados
4. Adicionar consulta
5. Consultar protocolo
6. Processo completo

### 📖 Documentação: [README.md](README.md)

---

## 🎭 Abordagem 2: Playwright (Portal Gov)

### ✅ Vantagens:
- Acesso direto ao portal do governo
- Não depende de APIs terceiras
- Gratuito
- Acesso a qualquer município

### ⚠️ Desvantagens:
- Pode exigir seleção manual de certificado (1ª vez)
- Mais lento
- Depende da estrutura do site
- Pode quebrar com atualizações do portal

### 🔧 Como funciona:

1. **Instala o certificado no Windows** (automático)
2. **Configura o Chrome** para auto-seleção
3. **Acessa o portal** e clica em "Acesso via certificado digital"
4. **Seleciona o certificado** (pode ser automático se configurado)
5. **Navega até Notas Recebidas**
6. **Baixa XMLs e PDFs**

### 📝 Como usar:

```bash
python nfse_playwright_agent.py
```

O script vai solicitar:
- Caminho do certificado .pfx
- Senha do certificado
- Diretório de download
- Quantidade de notas

### 🎯 Seleção Automática de Certificado

O código tenta configurar o Chrome para **auto-selecionar** o certificado:

```python
# Cria perfil do Chrome com preferências
preferences = {
    "profile": {
        "content_settings": {
            "exceptions": {
                "auto_select_certificate": {
                    "https://www.nfse.gov.br:443,*": {
                        "setting": 1
                    }
                }
            }
        }
    }
}
```

**⚠️ IMPORTANTE:**
- Na **primeira vez**, pode aparecer a janela do Windows para selecionar o certificado
- Selecione manualmente e marque "Lembrar sempre"
- Nas próximas execuções, será automático

### 🔐 Como funciona a instalação do certificado:

```powershell
# PowerShell (executado automaticamente pelo script)
$pwd = ConvertTo-SecureString -String 'senha' -Force -AsPlainText
Import-PfxCertificate -FilePath 'cert.pfx' -CertStoreLocation Cert:\CurrentUser\My -Password $pwd
```

---

## 📦 Instalação

### Dependências Comuns:
```bash
uv pip install requests python-dotenv
```

### Para API TecnoSpeed (main.py):
```bash
# Já instalado acima
```

### Para Playwright (nfse_playwright_agent.py):
```bash
uv pip install playwright pywin32
playwright install chromium
```

---

## 🎯 Qual usar?

### Use **API TecnoSpeed** (`main.py`) se:
- ✅ Seu município está na lista homologada
- ✅ Quer automação 100% sem interação
- ✅ Precisa de confiabilidade
- ✅ Vai usar em produção

### Use **Playwright** (`nfse_playwright_agent.py`) se:
- ✅ Quer acesso direto ao portal gov
- ✅ Não quer depender de APIs terceiras
- ✅ Seu município não está na API TecnoSpeed
- ✅ Não se importa com possível interação manual

---

## 📁 Estrutura do Projeto

```
py_nfse/
├── main.py                      # ← API TecnoSpeed (Recomendado)
├── nfse_playwright_agent.py     # ← Playwright + Portal Gov
├── pyproject.toml               # Dependências
├── README.md                    # Documentação completa
├── README_COMPARACAO.md         # Este arquivo
├── .env.example                 # Configurações
└── downloads/                   # XMLs e PDFs baixados
```

---

## 🐛 Troubleshooting

### Playwright - Certificado não selecionado:

**Problema:** Janela de seleção aparece toda vez

**Solução:**
1. Execute o script uma vez
2. Selecione o certificado manualmente
3. Marque "Lembrar sempre" ou "Always use this certificate"
4. Próximas execuções serão automáticas

### Playwright - Erro ao instalar certificado:

**Problema:** PowerShell não tem permissão

**Solução:**
```powershell
# Execute PowerShell como Administrador
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### API TecnoSpeed - Certificado não encontrado:

**Solução:**
1. Use opção 2 do menu: Cadastrar certificado
2. Depois use opção 4 ou 6 para consultar

---

## 📄 Licença

Fornecido como está, para fins educacionais e de automação.

## 🤝 Contribuições

Sugestões e melhorias são bem-vindas!
