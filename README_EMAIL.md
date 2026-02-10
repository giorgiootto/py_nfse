# Configuração de E-mail para Resumo de Processamento NFSe

## 📧 Funcionalidade Adicionada

O sistema agora envia automaticamente um e-mail ao final do processamento com:

- ✅ Total de usuários processados
- ✅ Total de notas encontradas
- ✅ Total de notas baixadas
- ✅ Total de notas gravadas no Oracle
- ❌ Usuários em que o login falhou (com mensagem de erro)
- 📊 Detalhamento completo por usuário

## ⚙️ Configuração no .env

Adicione as seguintes configurações no arquivo `.env`:

```env
# Configurações de Email
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USER=nfse@condor.com.br
SMTP_PASSWORD=sua_senha_aqui
EMAIL_FROM=nfse@condor.com.br
EMAIL_TO=giorgio.otto@condor.com.br;paloma.moreira@condor.com.br;despesa3@condor.com.br
```

### Descrição dos Parâmetros:

- **SMTP_SERVER**: Servidor SMTP (para Office365 use `smtp.office365.com`)
- **SMTP_PORT**: Porta SMTP (587 para TLS)
- **SMTP_USER**: Usuário para autenticação SMTP
- **SMTP_PASSWORD**: Senha do e-mail (⚠️ **importante configurar**)
- **EMAIL_FROM**: E-mail remetente
- **EMAIL_TO**: E-mails destinatários separados por ponto-e-vírgula (;)

## 📊 Formato do E-mail

O e-mail enviado contém:

### Resumo Geral
- Total de usuários processados
- Logins com sucesso vs. falhas
- Total de notas encontradas, baixadas e gravadas

### Tabela Detalhada
Para cada usuário:
- Código da loja
- CPF/CNPJ
- Status do login (✓ ou ✗)
- Quantidade de notas encontradas
- Quantidade de notas baixadas
- Quantidade gravada no Oracle
- Tempo de processamento
- Mensagem de erro (se houver)

## 🎨 Modelo de E-mail

O e-mail é enviado em formato HTML com:
- Cabeçalho com data/hora da execução
- Cards de resumo com estatísticas principais
- Tabela formatada com cores indicando sucesso/erro
- Rodapé informativo

## ⚠️ Importante

1. **Configure a senha do e-mail** no campo `SMTP_PASSWORD` no `.env`
2. Caso use Gmail, pode ser necessário gerar uma "senha de app"
3. Para Office365, use as credenciais normais do e-mail
4. Se não configurar o e-mail, o sistema funcionará normalmente, apenas não enviará o resumo

## 🔍 Rastreamento de Estatísticas

O sistema agora rastreia:

- **Notas encontradas**: Total de notas identificadas nas páginas
- **Notas baixadas**: Notas que foram baixadas com sucesso (XML e/ou PDF)
- **Notas gravadas no Oracle**: Notas que foram inseridas no banco de dados

## 🚀 Uso

Após configurar o `.env`, execute normalmente:

```bash
python nfse_playwright_agent.py
```

Ao final do processamento, o e-mail será enviado automaticamente para os destinatários configurados.
