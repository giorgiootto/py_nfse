"""
Agente NFSe com Playwright para download automático de notas fiscais
Acessa o portal https://www.nfse.gov.br/EmissorNacional/Login
Utiliza login via usuário e senha configurados na tabela CONF_MUNIC_NFSE do Oracle
"""

import os
import time
import subprocess
import tempfile
import winreg
import threading
import requests  # Para download direto via HTTP
import socket  # Para pegar nome da máquina
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Importar oracledb
try:
    import oracledb
    ORACLE_AVAILABLE = True
except ImportError:
    ORACLE_AVAILABLE = False
    print("⚠️  oracledb não instalado - gravação no Oracle desabilitada")
    print("   Instale com: pip install oracledb")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("⚠️  PyAutoGUI não disponível. Instale com: pip install pyautogui")

try:
    from pywinauto import Application
    from pywinauto.findwindows import find_windows
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False
    print("⚠️  PyWinAuto não disponível. Instale com: pip install pywinauto")


class NFSePlaywrightAgent:
    """Agente para automação de download de NFSe com login por usuário e senha"""
    
    PORTAL_URL = "https://www.nfse.gov.br/EmissorNacional/Login"
    
    def __init__(self, usuario: str, senha: str, codloja: int, download_dir: str = "./downloads"):
        """
        Inicializa o agente
        
        Args:
            usuario: CPF/CNPJ do usuário
            senha: Senha de acesso
            codloja: Código da loja
            download_dir: Diretório para downloads
        """
        self.usuario = usuario
        self.senha = senha
        self.codloja = codloja
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurações Oracle
        self.oracle_enabled = ORACLE_AVAILABLE and os.getenv("ORACLE_USER")
        self.oracle_user = os.getenv("ORACLE_USER")
        self.oracle_password = os.getenv("ORACLE_PASSWORD")
        self.oracle_dsn = os.getenv("ORACLE_DSN")
        self.oracle_connection = None
        
        # Informações da máquina para log
        self.machine_name = socket.gethostname()
        self.machine_ip = socket.gethostbyname(self.machine_name)
        self.usuario_log = f"{self.machine_name} ({self.machine_ip})"
        
        if self.oracle_enabled:
            print(f"✓ Oracle habilitado: {self.oracle_user}@{self.oracle_dsn}")
        else:
            print("⚠️  Oracle desabilitado - arquivos só serão salvos localmente")
    
    def _auto_click_certificate_dialog(self, timeout: int = 30) -> bool:
        """
        Detecta e clica automaticamente no botão OK da janela de certificado
        usando pywinauto para automação robusta do Windows
        
        Args:
            timeout: Tempo máximo de espera em segundos
            
        Returns:
            True se conseguiu clicar
        """
        if not PYWINAUTO_AVAILABLE:
            print("⚠️  PyWinAuto não disponível - tentando método alternativo")
            return self._auto_click_certificate_simple(timeout)
        
        try:
            print("\n→ Procurando janela de certificado...")
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    # Procurar janela com título contendo "certificado" (case insensitive)
                    windows = find_windows(title_re=".*[Cc]ertificado.*")
                    
                    if windows:
                        hwnd = windows[0]
                        print(f"✓ Janela de certificado encontrada (HWND: {hwnd})")
                        
                        # Conectar à janela
                        app = Application(backend="win32").connect(handle=hwnd)
                        dlg = app.window(handle=hwnd)
                        
                        # Aguardar janela estar pronta
                        dlg.wait('ready', timeout=5)
                        time.sleep(1)
                        
                        # Tentar selecionar o primeiro item da lista (se houver)
                        try:
                            # Procurar por ListView ou ListBox
                            if dlg.child_window(class_name="SysListView32").exists():
                                list_view = dlg.child_window(class_name="SysListView32")
                                list_view.set_focus()
                                list_view.type_keys("{HOME}")  # Ir para o primeiro item
                                time.sleep(0.5)
                                print("✓ Certificado selecionado na lista")
                        except:
                            pass
                        
                        # Procurar e clicar no botão OK
                        try:
                            # Tentar várias formas de encontrar o botão OK
                            ok_button = None
                            
                            # Método 1: Por texto "OK"
                            try:
                                ok_button = dlg.child_window(title="OK", class_name="Button")
                            except:
                                pass
                            
                            # Método 2: Por texto "&OK" (com hotkey)
                            if not ok_button or not ok_button.exists():
                                try:
                                    ok_button = dlg.child_window(title_re=".*OK.*", class_name="Button")
                                except:
                                    pass
                            
                            # Método 3: Pressionar Enter (mais seguro)
                            if ok_button and ok_button.exists():
                                ok_button.click()
                                print("✓ Botão OK clicado!")
                                return True
                            else:
                                # Fallback: pressionar Enter
                                dlg.type_keys("{ENTER}")
                                print("✓ Enter pressionado (botão OK não encontrado)")
                                return True
                                
                        except Exception as e:
                            print(f"⚠️  Erro ao clicar OK, tentando Enter: {e}")
                            dlg.type_keys("{ENTER}")
                            return True
                            
                except Exception as e:
                    pass
                
                time.sleep(0.5)
            
            print("⚠️  Janela de certificado não encontrada no timeout")
            return False
            
        except Exception as e:
            print(f"⚠️  Erro na automação: {e}")
            return False
    
    def _auto_click_certificate_simple(self, timeout: int = 30) -> bool:
        """
        Método alternativo simples usando pyautogui (fallback)
        """
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        print("\n→ Procurando janela de certificado...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Procurar pelo botão OK na tela
                button_location = None
                
                # Tentar encontrar o texto "OK" na tela
                try:
                    button_location = pyautogui.locateOnScreen('ok_button.png', confidence=0.8)
                except:
                    pass
                
                # Se não encontrar pela imagem, tentar por coordenadas aproximadas
                # A janela geralmente aparece centralizada
                if button_location is None:
                    # Obter dimensões da tela
                    screen_width, screen_height = pyautogui.size()
                    
                    # Posição aproximada do botão OK (centro-direita da janela)
                    # Baseado na imagem fornecida
                    x = screen_width // 2 + 100  # Aproximadamente 100px à direita do centro
                    y = screen_height // 2 + 130  # Aproximadamente 130px abaixo do centro
                    
                    # Mover mouse para a posição e verificar se há botão
                    pyautogui.moveTo(x, y, duration=0.5)
                    time.sleep(0.3)
                    
                    # Clicar
                    pyautogui.click(x, y)
                    print(f"✓ Clicou em posição aproximada do botão OK ({x}, {y})")
                    
                    time.sleep(2)  # Aguardar processamento
                    return True
                else:
                    # Se encontrou pela imagem, clicar no centro
                    button_x = button_location.left + button_location.width // 2
                    button_y = button_location.top + button_location.height // 2
                    pyautogui.click(button_x, button_y)
                    print("✓ Botão OK clicado (detectado por imagem)")
                    return True
                    
            except Exception as e:
                pass
            
            time.sleep(0.5)  # Aguardar antes de tentar novamente
        
        print("⚠️  Não foi possível encontrar o botão OK automaticamente")
        return False
    
    def _conectar_oracle(self) -> bool:
        """Conecta ao Oracle se ainda não conectado"""
        if not self.oracle_enabled:
            return False
        
        try:
            if self.oracle_connection is None or not self.oracle_connection.ping():
                self.oracle_connection = oracledb.connect(
                    user=self.oracle_user,
                    password=self.oracle_password,
                    dsn=self.oracle_dsn
                )
            return True
        except Exception as e:
            print(f"⚠️  Erro ao conectar Oracle: {e}")
            self._log_oracle('ERROR', 'AGENT', f"Erro conexão: {e}", None)
            return False
    
    def _log_oracle(self, nivel: str, origem: str, mensagem: str, chave: Optional[str]):
        """
        Grava log no Oracle
        
        Args:
            nivel: ERROR, WARN, INFO, DEBUG
            origem: Nome do processo/origem
            mensagem: Mensagem de log
            chave: Chave do documento (opcional)
        """
        if not self.oracle_enabled:
            return
        
        try:
            if not self._conectar_oracle():
                return
            
            cursor = self.oracle_connection.cursor()
            cursor.execute("""
                INSERT INTO ADM.log_processamento 
                (nivel, origem, mensagem, chave_documento, usuario)
                VALUES (:nivel, :origem, :mensagem, :chave, :usuario)
            """, {
                'nivel': nivel,
                'origem': origem,
                'mensagem': mensagem[:4000],  # Limitar a 4000 chars
                'chave': chave,
                'usuario': self.usuario_log[:50]  # Limitar a 50 chars
            })
            self.oracle_connection.commit()
            cursor.close()
        except Exception as e:
            print(f"⚠️  Erro ao gravar log: {e}")
    
    def _existe_no_oracle(self, chave: str) -> bool:
        """Verifica se a chave já existe no Oracle"""
        if not self.oracle_enabled:
            return False
        
        try:
            if not self._conectar_oracle():
                return False
            
            cursor = self.oracle_connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM down_nfse WHERE CHAVE = :chave
            """, {'chave': chave})
            result = cursor.fetchone()
            cursor.close()
            return result[0] > 0
        except Exception as e:
            self._log_oracle('ERROR', 'AGENT', f"Erro verificar existência: {e}", chave)
            return False
    
    def _gravar_oracle(self, chave: str, xml_path: Path, pdf_path: Path) -> bool:
        """
        Grava XML e PDF no Oracle
        
        Args:
            chave: Chave da NFSe (50 dígitos)
            xml_path: Caminho do arquivo XML
            pdf_path: Caminho do arquivo PDF
            
        Returns:
            True se gravado com sucesso
        """
        if not self.oracle_enabled:
            return False
        
        try:
            # Verificar se já existe
            if self._existe_no_oracle(chave):
                print(f"    ⊘ Já existe no Oracle: {chave}")
                return True
            
            if not self._conectar_oracle():
                return False
            
            # Ler arquivos
            xml_content = xml_path.read_text(encoding='utf-8') if xml_path.exists() else None
            pdf_content = pdf_path.read_bytes() if pdf_path.exists() else None
            
            if not xml_content and not pdf_content:
                self._log_oracle('WARN', 'AGENT', 'Nenhum arquivo para gravar', chave)
                return False
            
            # Inserir no banco
            cursor = self.oracle_connection.cursor()
            cursor.execute("""
                INSERT INTO down_nfse 
                (DOCXML, DOCBLOB, ORIGEM, SITUACAO, CHAVE)
                VALUES (:xml, :pdf, :origem, :situacao, :chave)
            """, {
                'xml': xml_content,
                'pdf': pdf_content,
                'origem': 'AGENT',
                'situacao': 0,
                'chave': chave
            })
            self.oracle_connection.commit()
            cursor.close()
            
            print(f"    ✓ Gravado no Oracle: {chave}")
            self._log_oracle('INFO', 'AGENT', f'NFSe gravada com sucesso', chave)
            return True
            
        except Exception as e:
            print(f"    ✗ Erro ao gravar no Oracle: {e}")
            self._log_oracle('ERROR', 'AGENT', f"Erro ao gravar: {e}", chave)
            return False
    
    def _configure_chrome_registry_policy(self, cert_info: dict) -> bool:
        """
        Configura política do Chrome no Registry do Windows para auto-seleção de certificado
        
        Args:
            cert_info: Informações do certificado
            
        Returns:
            True se configurado com sucesso
        """
        try:
            print("\n→ Configurando política AutoSelectCertificateForUrls no Registry...")
            
            # Extrair CN do Issuer para o filtro
            issuer_cn = "AC"  # Default
            if cert_info and 'Issuer' in cert_info:
                issuer = cert_info['Issuer']
                # Extrair CN do Issuer (ex: CN=AC Certisign RFB G5)
                import re
                match = re.search(r'CN=([^,]+)', issuer)
                if match:
                    issuer_cn = match.group(1).strip()
            
            # Formato da política: JSON string com padrão e filtro
            # O filtro pode ser por ISSUER.CN ou SUBJECT.CN
            policy_value = f'{{"pattern":"https://www.nfse.gov.br","filter":{{}}}}'
            
            print(f"   Issuer CN detectado: {issuer_cn}")
            print(f"   Política: {policy_value}")
            
            # Comando PowerShell para criar a chave no Registry
            ps_command = f"""
            # Criar chave de políticas do Chrome (usuário atual)
            $regPath = "HKCU:\\SOFTWARE\\Policies\\Google\\Chrome"
            $regKey = "AutoSelectCertificateForUrls"
            
            # Criar estrutura se não existir
            if (!(Test-Path $regPath)) {{
                New-Item -Path $regPath -Force | Out-Null
                Write-Host "Chave de políticas criada"
            }}
            
            # Criar a subchave para lista de valores
            $policyPath = "$regPath\\$regKey"
            if (!(Test-Path $policyPath)) {{
                New-Item -Path $policyPath -Force | Out-Null
            }}
            
            # Adicionar o valor (índice 1)
            Set-ItemProperty -Path $policyPath -Name "1" -Value '{policy_value}' -Type String
            
            Write-Host "Política AutoSelectCertificateForUrls configurada com sucesso"
            """
            
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print("✓ Política do Chrome configurada no Registry")
                print("   IMPORTANTE: Feche todos os Chrome abertos e reinicie")
                return True
            else:
                print(f"⚠️  Erro ao configurar Registry: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"⚠️  Erro ao configurar política: {e}")
            return False
    
    def _get_certificate_info(self) -> dict:
        """
        Extrai informações do certificado .pfx usando PowerShell
        
        Returns:
            Dicionário com subject, issuer, thumbprint do certificado
        """
        try:
            print("\n→ Extraindo informações do certificado...")
            
            ps_command = f"""
            $pwd = ConvertTo-SecureString -String '{self.pfx_password}' -Force -AsPlainText
            $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2('{self.pfx_path.absolute()}', $pwd)
            
            # Extrair CN do Subject (apenas o nome)
            $subject = $cert.Subject
            $issuer = $cert.Issuer
            $thumbprint = $cert.Thumbprint
            
            # Extrair apenas o CN (Common Name)
            if ($subject -match 'CN=([^,]+)') {{
                $cn = $matches[1]
            }} else {{
                $cn = $subject
            }}
            
            # Retornar JSON
            @{{
                Subject = $cn
                Issuer = $issuer
                Thumbprint = $thumbprint
                FullSubject = $subject
            }} | ConvertTo-Json -Compress
            """
            
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                import json
                cert_info = json.loads(result.stdout.strip())
                print(f"✓ Certificado: {cert_info['Subject']}")
                return cert_info
            else:
                print(f"⚠️  Não foi possível extrair info do certificado")
                return {}
                
        except Exception as e:
            print(f"⚠️  Erro ao extrair info: {e}")
            return {}
    
    def _install_certificate_windows(self) -> bool:
        """
        Instala o certificado .pfx no Windows (CurrentUser\\My)
        
        Returns:
            True se instalado com sucesso
        """
        try:
            print("\n→ Instalando certificado no Windows...")
            
            # Comando PowerShell para importar o certificado
            ps_command = f"""
            $pwd = ConvertTo-SecureString -String '{self.pfx_password}' -Force -AsPlainText
            Import-PfxCertificate -FilePath '{self.pfx_path.absolute()}' -CertStoreLocation Cert:\\CurrentUser\\My -Password $pwd -Exportable
            """
            
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print("✓ Certificado instalado no Windows")
                return True
            else:
                print(f"✗ Erro ao instalar certificado: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"✗ Erro ao instalar certificado: {e}")
            return False
    
    def _uninstall_certificate_windows(self) -> bool:
        """
        Remove o certificado instalado do Windows Store (CurrentUser\\My)
        
        Returns:
            True se removido com sucesso
        """
        try:
            print("\n→ Removendo certificado do Windows Store...")
            
            # Obter thumbprint do certificado
            cert_info = self._get_certificate_info()
            if not cert_info or 'Thumbprint' not in cert_info:
                print("⚠️  Não foi possível obter thumbprint do certificado")
                return False
            
            thumbprint = cert_info['Thumbprint']
            
            # Comando PowerShell para remover o certificado pelo thumbprint
            ps_command = f"""
            $cert = Get-ChildItem -Path Cert:\\CurrentUser\\My | Where-Object {{ $_.Thumbprint -eq '{thumbprint}' }}
            if ($cert) {{
                Remove-Item -Path "Cert:\\CurrentUser\\My\\$($cert.Thumbprint)" -Force
                Write-Output "Removido"
            }} else {{
                Write-Output "NaoEncontrado"
            }}
            """
            
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if "Removido" in output:
                    print(f"✓ Certificado removido (Thumbprint: {thumbprint[:16]}...)")
                    return True
                elif "NaoEncontrado" in output:
                    print(f"⚠️  Certificado não encontrado no Windows Store")
                    return True  # Considerar sucesso se já não está lá
                else:
                    print(f"⚠️  Resposta inesperada: {output}")
                    return False
            else:
                print(f"✗ Erro ao remover certificado: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"✗ Erro ao remover certificado: {e}")
            return False
    
    def _configure_chrome_auto_select(self, cert_info: dict) -> Optional[str]:
        """
        Configura o Chrome para selecionar automaticamente o certificado específico
        
        Args:
            cert_info: Dicionário com informações do certificado (subject, issuer, thumbprint)
            
        Returns:
            Caminho do diretório do perfil do Chrome
        """
        try:
            print("\n→ Configurando auto-seleção de certificado no Chrome...")
            
            # Criar diretório temporário para perfil do Chrome
            profile_dir = Path(tempfile.mkdtemp(prefix="chrome_nfse_"))
            
            # Criar estrutura do perfil
            default_dir = profile_dir / "Default"
            default_dir.mkdir(parents=True, exist_ok=True)
            
            # Configurar preferências do Chrome para auto-selecionar certificado
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
            
            # Salvar preferências
            prefs_file = default_dir / "Preferences"
            import json
            with open(prefs_file, 'w') as f:
                json.dump(preferences, f, indent=2)
            
            print(f"✓ Perfil Chrome configurado em: {profile_dir}")
            
            # Configurar política do Chrome via arquivo JSON (método mais confiável)
            # AutoSelectCertificateForUrls com filtro específico
            if cert_info:
                print(f"   Certificado configurado: {cert_info.get('Subject', 'N/A')}")
            
            return str(profile_dir)
            
        except Exception as e:
            print(f"✗ Erro ao configurar auto-seleção: {e}")
            return None
    
    def _setup_browser(self):
        """
        Configura o navegador Chromium
        
        Returns:
            Tupla (context, page, playwright)
        """
        print("\n→ Iniciando navegador...")
        
        playwright = sync_playwright().start()
        
        # Argumentos do Chrome
        browser_args = [
            "--ignore-certificate-errors",
            "--disable-web-security",
            "--allow-insecure-localhost",
            "--disable-blink-features=AutomationControlled",
            "--use-system-default-printer",
            "--enable-features=WebUIDarkMode",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        
        # Lançar navegador
        browser = playwright.chromium.launch(
            headless=False,
            args=browser_args,
            slow_mo=500
        )
        
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080}
        )
        
        page = context.new_page()
        
        print("✓ Navegador iniciado")
        return context, page, playwright
    
    def login_com_usuario_senha(self, page: Page) -> bool:
        """
        Realiza login com usuário e senha
        
        Args:
            page: Página do Playwright
            
        Returns:
            True se login bem-sucedido
        """
        try:
            print("\n→ Acessando portal NFSe...")
            page.goto(self.PORTAL_URL, wait_until="networkidle")
            time.sleep(3)
            
            print(f"   URL atual: {page.url}")
            print(f"   Título: {page.title()}")
            
            print(f"\n→ Fazendo login com usuário {self.usuario}...")
            
            # Preencher campo de usuário (CPF/CNPJ)
            try:
                print("   → Preenchendo campo de usuário/CPF/CNPJ...")
                campo_usuario = page.locator('#Inscricao')
                campo_usuario.wait_for(state='visible', timeout=10000)
                campo_usuario.fill(self.usuario)
                print(f"   ✓ Usuário preenchido: {self.usuario}")
            except Exception as e:
                print(f"   ✗ Erro ao preencher usuário: {e}")
                return False
            
            # Preencher campo de senha
            try:
                print("   → Preenchendo campo de senha...")
                campo_senha = page.locator('#Senha')
                campo_senha.wait_for(state='visible', timeout=10000)
                campo_senha.fill(self.senha)
                print("   ✓ Senha preenchida")
            except Exception as e:
                print(f"   ✗ Erro ao preencher senha: {e}")
                return False
            
            # Clicar no botão Entrar
            try:
                print("   → Clicando no botão 'Entrar'...")
                botao_entrar = page.locator('button[type="submit"].btn.btn-lg.btn-primary')
                botao_entrar.wait_for(state='visible', timeout=10000)
                time.sleep(1)
                botao_entrar.click()
                print("   ✓ Botão 'Entrar' clicado")
            except Exception as e:
                print(f"   ✗ Erro ao clicar no botão Entrar: {e}")
                return False
            
            # Aguardar redirecionamento após login
            print("\n→ Aguardando conclusão do login...")
            time.sleep(5)
            page.wait_for_load_state("networkidle", timeout=60000)
            
            # Verificar se login foi bem-sucedido
            success_indicators = [
                'text=Notas Recebidas',
                'text=Notas Emitidas',
                'text=Bem-vindo',
                '.user-info',
                'button:has-text("Sair")',
                'a:has-text("Sair")'
            ]
            
            for indicator in success_indicators:
                try:
                    if page.locator(indicator).count() > 0:
                        print("✓ Login realizado com sucesso!")
                        return True
                except:
                    continue
            
            # Verificar pela URL
            current_url = page.url
            print(f"   URL após login: {current_url}")
            
            if "Login" not in current_url:
                print("✓ Login assumido como bem-sucedido (redirecionado)")
                return True
            
            # Verificar se há mensagem de erro
            try:
                erros = page.locator('.alert-danger, .error, .validation-summary-errors').all()
                if len(erros) > 0:
                    for erro in erros:
                        texto_erro = erro.inner_text()
                        print(f"   ✗ Erro na página: {texto_erro}")
                    return False
            except:
                pass
            
            print("⚠️  Não foi possível confirmar o login automaticamente")
            return False
            
        except Exception as e:
            print(f"✗ Erro durante login: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def navegar_notas_recebidas(self, page: Page, dias_retroativos: int = 10) -> bool:
        """
        Navega até a seção de Notas Recebidas e aplica filtro de data
        
        Args:
            page: Página do Playwright
            dias_retroativos: Quantidade de dias para trás (padrão: 10)
            
        Returns:
            True se navegação bem-sucedida
        """
        try:
            print("\n→ Navegando para Notas Recebidas...")
            
            # Navegar diretamente para a URL
            page.goto("https://www.nfse.gov.br/EmissorNacional/Notas/Recebidas", wait_until="networkidle")
            print("✓ Página de Notas Recebidas carregada")
            
            time.sleep(3)  # Aguardar renderização completa
            
            # Calcular datas
            data_final = datetime.now()
            data_inicial = data_final - timedelta(days=dias_retroativos)
            
            # Formatar datas
            formato_br = data_inicial.strftime("%d/%m/%Y")
            formato_br_final = data_final.strftime("%d/%m/%Y")
            
            print(f"\n→ Aplicando filtro de data:")
            print(f"   Data inicial: {formato_br} (últimos {dias_retroativos} dias)")
            print(f"   Data final: {formato_br_final} (hoje)")
            
            # Usar os seletores exatos fornecidos
            try:
                # Preencher data inicial: id="datainicio"
                campo_inicial = page.locator('#datainicio')
                if campo_inicial.count() > 0:
                    campo_inicial.click()
                    campo_inicial.fill(formato_br)
                    print(f"   ✓ Data inicial preenchida: {formato_br}")
                else:
                    print("   ⚠️  Campo data inicial não encontrado")
            except Exception as e:
                print(f"   ⚠️  Erro ao preencher data inicial: {e}")
            
            time.sleep(0.5)
            
            try:
                # Preencher data final: id="datafim"
                campo_final = page.locator('#datafim')
                if campo_final.count() > 0:
                    campo_final.click()
                    campo_final.fill(formato_br_final)
                    print(f"   ✓ Data final preenchida: {formato_br_final}")
                else:
                    print("   ⚠️  Campo data final não encontrado")
            except Exception as e:
                print(f"   ⚠️  Erro ao preencher data final: {e}")
            
            time.sleep(0.5)
            
            # Clicar no botão Filtrar: button[type="submit"].btn.btn-primary
            print("\n→ Clicando no botão Filtrar...")
            try:
                botao_filtrar = page.locator('button[type="submit"].btn.btn-primary')
                if botao_filtrar.count() > 0:
                    botao_filtrar.first.click()
                    print("   ✓ Botão Filtrar clicado")
                else:
                    print("   ⚠️  Botão Filtrar não encontrado")
                    input("   Por favor, clique manualmente e pressione ENTER...")
            except Exception as e:
                print(f"   ⚠️  Erro ao clicar Filtrar: {e}")
                input("   Por favor, clique manualmente e pressione ENTER...")
            
            # Aguardar resultados
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)
            
            print("✓ Filtro aplicado com sucesso")
            return True
            
        except Exception as e:
            print(f"✗ Erro ao navegar/filtrar: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def baixar_ultimas_notas(self, page: Page, quantidade: int = 999999) -> int:
        """
        Baixa XMLs e PDFs de todas as notas, navegando por todas as páginas
        
        Args:
            page: Página do Playwright
            quantidade: Quantidade máxima de notas (padrão: ilimitado)
            
        Returns:
            Quantidade de notas processadas
        """
        try:
            print(f"\n→ Baixando TODAS as notas (navegando por todas as páginas)...")
            
            total_downloaded = 0
            pagina_atual = 1
            processo_start_time = time.time()  # Tempo de início do processo
            notas_pagina_anterior = set()  # Para detectar páginas repetidas
            
            while total_downloaded < quantidade:
                print(f"\n{'='*60}")
                print(f"  PÁGINA {pagina_atual}")
                print(f"{'='*60}")
                
                # Aguardar carregamento da lista
                time.sleep(3)
                
                # Tentar encontrar linhas/cards de notas
                row_selectors = [
                    'div.list-group-item',  # Cards com list-group-item
                    'div.nota-item',
                    'tr:has(td)',  # Linhas de tabela
                    'div[data-nota]',
                    '.resultado-nota'
                ]
                
                rows = []
                for selector in row_selectors:
                    try:
                        elements = page.locator(selector).all()
                        if len(elements) > 0:
                            # Limitar pela quantidade restante
                            quantidade_restante = quantidade - total_downloaded
                            rows = elements[:quantidade_restante]
                            print(f"✓ Encontradas {len(elements)} notas nesta página (processando {len(rows)})")
                            break
                    except:
                        continue
                
                if not rows:
                    print("⚠️  Nenhuma nota encontrada nesta página")
                    break
                
                print(f"✓ Encontradas {len(rows)} notas nesta página")
                
                # Coletar números das notas desta página para detectar loop
                notas_pagina_atual = set()
                
                # Processar cada nota da página
                notas_tentadas = 0  # Contador de notas tentadas (incluindo existentes)
                novas_baixadas = 0  # Contador de novas notas baixadas
                
                for idx, row in enumerate(rows, 1):
                    nota_start_time = time.time()
                    notas_tentadas += 1
                    try:
                        tempo_total = time.time() - processo_start_time
                        minutos = int(tempo_total // 60)
                        segundos = int(tempo_total % 60)
                        print(f"\n  [{total_downloaded + 1}] Processando nota {idx}/{len(rows)} da página {pagina_atual}... [Tentadas: {notas_tentadas}, Novas: {novas_baixadas}] [Tempo: {minutos}m {segundos}s]")
                        
                        # PASSO 0: SCROLL para tornar a linha visível
                        try:
                            row.scroll_into_view_if_needed(timeout=5000)
                            time.sleep(0.3)
                        except Exception as e:
                            print(f"    ⚠️  Erro ao rolar linha: {e}")
                        
                        # NOVA ABORDAGEM: Extrair número da nota DIRETO da linha, sem abrir menu
                        print(f"    → Extraindo número da nota...")
                        nota_numero = None
                        
                        # Tentar extrair de links existentes (mesmo invisíveis)
                        try:
                            # Procurar qualquer link com "Download" na linha
                            links = row.locator('a[href*="Download"]').all()
                            if len(links) > 0:
                                href = links[0].get_attribute('href')
                                if href:
                                    parts = href.split('/')
                                    nota_numero = parts[-1]
                                    print(f"    ✓ Número extraído do link ({len(nota_numero)} dígitos): {nota_numero}")
                        except:
                            pass
                        
                        # Alternativa: procurar texto do número na linha
                        if not nota_numero:
                            try:
                                texto = row.inner_text()
                                # Procurar número de 50 dígitos (padrão da NFSe)
                                import re
                                match = re.search(r'\b(\d{50})\b', texto)
                                if match:
                                    nota_numero = match.group(1)
                                    print(f"    ✓ Número extraído do texto (50 dígitos): {nota_numero}")
                                else:
                                    # Fallback: 44 ou 48 dígitos
                                    match = re.search(r'\b(\d{44,50})\b', texto)
                                    if match:
                                        nota_numero = match.group(1)
                                        print(f"    ✓ Número extraído do texto ({len(nota_numero)} dígitos): {nota_numero}")
                            except:
                                pass
                        
                        # Validar tamanho do número
                        if nota_numero and len(nota_numero) > 50:
                            print(f"    ⚠️  Número muito longo ({len(nota_numero)} dígitos) - tentando corrigir...")
                            # NFSe geralmente tem 44 ou 50 dígitos, pegar os primeiros
                            import re
                            matches = re.findall(r'\d{44,50}', nota_numero)
                            if matches:
                                nota_numero = matches[0]
                                print(f"    → Corrigido para: {nota_numero} ({len(nota_numero)} dígitos)")
                        
                        if not nota_numero:
                            print(f"    ⚠️  Não conseguiu extrair número da nota - PULANDO")
                            continue
                        
                        # Adicionar ao set de notas desta página
                        notas_pagina_atual.add(nota_numero)
                        
                        # Verificar timeout
                        if time.time() - nota_start_time > 30:
                            print(f"    ⚠️  TIMEOUT de 30s - PULANDO nota")
                            continue
                        
                        # PASSO 1: Baixar XML direto (SEM ABRIR MENU!)
                        print(f"    → Baixando XML diretamente...")
                        xml_start = time.time()
                        xml_downloaded = self._download_file_direct(page, nota_numero, "XML")
                        xml_elapsed = time.time() - xml_start
                        print(f"    → Download XML: {xml_elapsed:.1f}s")
                        
                        # PASSO 2: Baixar PDF direto (SEM ABRIR MENU!)
                        print(f"    → Baixando PDF diretamente...")
                        pdf_start = time.time()
                        pdf_downloaded = self._download_file_direct(page, nota_numero, "PDF")
                        pdf_elapsed = time.time() - pdf_start
                        print(f"    → Download PDF: {pdf_elapsed:.1f}s")
                        
                        # PASSO 3: Gravar no Oracle (se habilitado)
                        if self.oracle_enabled and (xml_downloaded or pdf_downloaded):
                            print(f"    → Gravando no Oracle...")
                            xml_path = self.download_dir / f"{nota_numero}.xml"
                            pdf_path = self.download_dir / f"{nota_numero}.pdf"
                            self._gravar_oracle(nota_numero, xml_path, pdf_path)
                        
                        # Contar apenas novos downloads (não existentes)
                        if xml_downloaded or pdf_downloaded:
                            total_downloaded += 1
                            if xml_downloaded and not pdf_downloaded:
                                novas_baixadas += 1  # Só XML novo
                            elif not xml_downloaded and pdf_downloaded:
                                novas_baixadas += 1  # Só PDF novo
                            elif xml_downloaded and pdf_downloaded:
                                novas_baixadas += 1  # Ambos novos
                        
                        # Aguardar antes da próxima nota
                        time.sleep(0.5)
                        
                        # Log de tempo gasto
                        elapsed = time.time() - nota_start_time
                        print(f"    ⏱️  Tempo gasto: {elapsed:.1f}s")
                        
                    except Exception as e:
                        print(f"    ✗ ERRO ao processar nota: {e}")
                        import traceback
                        traceback.print_exc()
                        # Tentar fechar menu mesmo com erro
                        try:
                            page.keyboard.press("Escape")
                            time.sleep(0.5)
                        except:
                            pass
                        continue
                
                # VERIFICAR SE ESTÁ EM LOOP (mesmas notas da página anterior)
                if notas_pagina_atual and notas_pagina_atual == notas_pagina_anterior:
                    print(f"\n{'='*60}")
                    print(f"⚠️  LOOP DETECTADO: Mesmas notas da página anterior!")
                    print(f"   Última página real foi: {pagina_atual}")
                    print(f"   Parando navegação...")
                    print(f"{'='*60}")
                    break
                
                # Atualizar notas da página anterior para próxima iteração
                notas_pagina_anterior = notas_pagina_atual.copy()
                
                # Verificar se já baixou o suficiente
                if total_downloaded >= quantidade:
                    print(f"\n✓ Processamento concluído")
                    break
                
                # PASSO 4: Tentar ir para próxima página
                print(f"\n{'='*60}")
                print(f"→ Procurando link para próxima página...")
                
                # Limpar qualquer modal/menu aberto antes de navegar
                print(f"    → Limpando menus/modais antes de mudar de página...")
                try:
                    for _ in range(5):
                        page.keyboard.press("Escape", timeout=1000)
                        time.sleep(0.2)
                except:
                    pass
                
                # Scroll para o topo antes de procurar paginação
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(0.5)
                except:
                    pass
                
                next_page_selectors = [
                    'a[href*="pg="]:has(i.fa-angle-right)',
                    'a[data-original-title="Próxima"]',
                    'a[title*="Próxima"]',
                    'a:has-text("Próxima")',
                    'a.pagination-next',
                    'li.next a'
                ]
                
                next_page_found = False
                for selector in next_page_selectors:
                    try:
                        links = page.locator(selector).all()
                        if len(links) > 0:
                            link = links[0]
                            if link.is_visible():
                                print(f"    ✓ Link encontrado - Indo para página {pagina_atual + 1}...")
                                link.click()
                                print(f"    → Aguardando carregamento...")
                                page.wait_for_load_state("networkidle", timeout=30000)
                                pagina_atual += 1
                                next_page_found = True
                                time.sleep(3)  # Aguardar estabilização da nova página
                                print(f"    ✓ Página {pagina_atual} carregada")
                                break
                    except Exception as e:
                        print(f"    ⚠️  Erro ao navegar: {e}")
                        continue
                
                if not next_page_found:
                    print("    ✓ Não há mais páginas - Download completo!")
                    break
            
            print(f"\n{'='*60}")
            print(f"✓ Total de notas processadas: {total_downloaded}")
            print(f"✓ Arquivos salvos em: {self.download_dir}")
            print(f"{'='*60}")
            
            return total_downloaded
            
        except Exception as e:
            print(f"✗ Erro ao baixar notas: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def _download_file_direct(self, page: Page, nota_numero: str, file_type: str) -> bool:
        """
        Baixa arquivo diretamente via HTTP sem abrir menu
        
        Args:
            page: Página do Playwright
            nota_numero: Número da nota (44-50 dígitos)
            file_type: "XML" ou "PDF"
            
        Returns:
            True se baixado com sucesso
        """
        try:
            # Construir URL baseado no tipo
            if file_type == "XML":
                url_path = f"/Notas/Download/NFSe/{nota_numero}"
                extensao = ".xml"
            else:  # PDF
                url_path = f"/Notas/Download/DANFSe/{nota_numero}"
                extensao = ".pdf"
            
            filepath = self.download_dir / f"{nota_numero}{extensao}"
            
            # Verificar se já existe
            if filepath.exists():
                print(f"    ⊘ {file_type} já existe: {nota_numero}{extensao}")
                return False
            
            # Obter cookies para autenticação
            cookies = page.context.cookies()
            session = requests.Session()
            for cookie in cookies:
                session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
            
            # URL completa - CORRIGIR duplicação
            # page.url é algo como: https://www.nfse.gov.br/EmissorNacional/Notas/Recebidas?pg=2
            # Queremos: https://www.nfse.gov.br/EmissorNacional/Notas/Download/NFSe/...
            base_url = page.url.split('/Notas')[0]  # https://www.nfse.gov.br/EmissorNacional
            full_url = base_url + url_path
            
            print(f"    → URL: {full_url}")
            
            # Download via HTTP
            response = session.get(full_url, timeout=10, stream=True)
            
            print(f"    → Status HTTP: {response.status_code}")
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                if filepath.exists() and filepath.stat().st_size > 0:
                    print(f"    ✓ {file_type} baixado: {nota_numero}{extensao} ({filepath.stat().st_size} bytes)")
                    return True
                else:
                    print(f"    ✗ {file_type} vazio")
                    return False
            elif response.status_code == 404:
                print(f"    ⚠️  {file_type} não encontrado no servidor (HTTP 404)")
                print(f"    → Possível que esta nota não tenha {file_type} disponível")
                return False
            else:
                print(f"    ⚠️  HTTP {response.status_code} para {file_type}")
                return False
                
        except Exception as e:
            print(f"    ✗ Erro ao baixar {file_type}: {e}")
            return False
    
    def _download_file(self, page: Page, row, file_type: str, url_pattern: str, selectors: list, keep_menu_open: bool = False) -> bool:
        """
        Baixa um arquivo (XML ou PDF) se ainda não existir
        
        Args:
            page: Página do Playwright
            row: Elemento da linha/card da nota
            file_type: Tipo do arquivo ("XML" ou "PDF")
            url_pattern: Padrão na URL (ex: "Download/NFSe")
            selectors: Lista de seletores para encontrar o link
            keep_menu_open: Se True, não fecha o menu após download (útil para baixar XML e PDF sequencialmente)
            
        Returns:
            True se arquivo foi baixado ou já existe
        """
        try:
            # Procurar o link dentro do row primeiro
            for selector in selectors:
                try:
                    links = row.locator(selector).all()
                    if len(links) > 0:
                        link = links[0]
                        
                        # Extrair número da nota da URL para usar como nome do arquivo
                        href = link.get_attribute('href')
                        if href:
                            # Extrair o número da NFSe da URL
                            # Ex: /EmissorNacional/Notas/Download/NFSe/41069022282040130000112000000000029926027515362055
                            parts = href.split('/')
                            if len(parts) > 0:
                                nota_numero = parts[-1]
                                
                                # Nome do arquivo baseado no número da nota
                                if file_type == "XML":
                                    filename = f"{nota_numero}.xml"
                                else:
                                    filename = f"{nota_numero}.pdf"
                                
                                filepath = self.download_dir / filename
                                
                                # Verificar se arquivo já existe
                                if filepath.exists():
                                    print(f"    ⏭️  {file_type} já existe: {filename}")
                                    return True
                                
                                # NOVA ABORDAGEM: Download direto via HTTP
                                print(f"    ↓ Baixando {file_type} via HTTP...")
                                try:
                                    # Obter cookies para autenticação
                                    cookies = page.context.cookies()
                                    session = requests.Session()
                                    for cookie in cookies:
                                        session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
                                    
                                    # URL completa
                                    if href.startswith('http'):
                                        full_url = href
                                    else:
                                        base_url = page.url.split('/Notas')[0]
                                        full_url = base_url + href if href.startswith('/') else base_url + '/' + href
                                    
                                    # Download via requests
                                    response = session.get(full_url, timeout=10, stream=True)
                                    
                                    if response.status_code == 200:
                                        with open(filepath, 'wb') as f:
                                            for chunk in response.iter_content(chunk_size=8192):
                                                f.write(chunk)
                                        
                                        if filepath.exists() and filepath.stat().st_size > 0:
                                            print(f"    ✓ {file_type} baixado: {filename} ({filepath.stat().st_size} bytes)")
                                            return True
                                    else:
                                        print(f"    ⚠️  HTTP {response.status_code} - tentando Playwright...")
                                        raise Exception("Fallback para Playwright")
                                        
                                except Exception as http_err:
                                    # Fallback: Playwright download
                                    print(f"    → Usando Playwright download...")
                                    try:# Scroll do link antes de clicar
                                        link.scroll_into_view_if_needed(timeout=3000)
                                        time.sleep(0.3)
                                        
                                        with page.expect_download(timeout=10000) as download_info:
                                            link.click(timeout=5000, force=True)
                                        
                                        download = download_info.value
                                        download.save_as(str(filepath))
                                        time.sleep(0.2)
                                        
                                        # Limpar download do navegador
                                        try:
                                            download.cancel()
                                        except:
                                            pass
                                        
                                        if filepath.exists():
                                            print(f"    ✓ {file_type} baixado: {filename}")
                                            # Não fechar menu se keep_menu_open=True
                                            if not keep_menu_open:
                                                try:
                                                    page.keyboard.press("Escape", timeout=1000)
                                                except:
                                                    pass
                                            print(f"    ✓ {file_type} baixado: {filename}")
                                            return True
                                    except Exception as pw_err:
                                        print(f"    ✗ Falha total: HTTP={http_err}, PW={pw_err}")
                                        return False
                        
                except Exception as e:
                    continue
            
            # Se não encontrou no row, tentar na página inteira (menu pode estar fora)
            for selector in selectors:
                try:
                    links = page.locator(selector).all()
                    for link in links:
                        if link.is_visible():
                            href = link.get_attribute('href')
                            if href:
                                parts = href.split('/')
                                if len(parts) > 0:
                                    nota_numero = parts[-1]
                                    
                                    if file_type == "XML":
                                        filename = f"{nota_numero}.xml"
                                    else:
                                        filename = f"{nota_numero}.pdf"
                                    
                                    filepath = self.download_dir / filename
                                    
                                    if filepath.exists():
                                        print(f"    ⏭️  {file_type} já existe: {filename}")
                                        return True
                                    
                                    with page.expect_download(timeout=15000) as download_info:
                                        link.click()
                                    
                                    download = download_info.value
                                    download.save_as(str(filepath))
                                    print(f"    ✓ {file_type} baixado: {filename}")
                                    return True
                except Exception as e:
                    continue
            
            print(f"    ⚠️  Link de {file_type} não encontrado")
            return False
            
        except Exception as e:
            print(f"    ⚠️  Erro ao baixar {file_type}: {e}")
            return False
    
    def executar(self, quantidade: int = 999999, dias_retroativos: int = 10):
        """
        Executa o processo completo
        
        Args:
            quantidade: Quantidade máxima de notas (padrão: todas)
            dias_retroativos: Dias para trás no filtro de data
        """
        context = None
        playwright = None
        
        try:
            print("="*70)
            print("  AGENTE NFSe - Download Automático de Notas")
            print(f"  Loja: {self.codloja} | Usuário: {self.usuario}")
            print("="*70)
            
            # 1. Configurar e iniciar navegador
            context, page, playwright = self._setup_browser()
            
            # 2. Login com usuário e senha
            if not self.login_com_usuario_senha(page):
                print("\n✗ Falha no login. Encerrando...")
                return
            
            # 3. Navegar para notas recebidas
            if not self.navegar_notas_recebidas(page, dias_retroativos):
                print("\n✗ Falha na navegação. Encerrando...")
                return
            
            # 4. Baixar notas
            downloaded = self.baixar_ultimas_notas(page, quantidade)
            
            print("\n" + "="*70)
            print("  PROCESSO CONCLUÍDO!")
            print(f"  Total de notas processadas: {downloaded}")
            print(f"  Arquivos em: {self.download_dir}")
            print("="*70)
            
            time.sleep(3)  # Aguardar 3 segundos antes de fechar
            
        except Exception as e:
            print(f"\n✗ Erro durante execução: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            if context:
                context.close()
            if playwright:
                playwright.stop()
            # Fechar conexão Oracle
            if self.oracle_connection:
                try:
                    self.oracle_connection.close()
                    print("✓ Conexão Oracle fechada")
                except:
                    pass


def processar_multiplos_usuarios(usuarios: List[dict], download_dir: str, dias_retroativos: int):
    """
    Processa múltiplos usuários em sequência
    
    Args:
        usuarios: Lista de dicionários com codloja, usuario, senha
        download_dir: Diretório de downloads
        dias_retroativos: Dias para trás no filtro
    """
    total_usuarios = len(usuarios)
    
    print("\n" + "="*70)
    print(f"  PROCESSANDO {total_usuarios} USUÁRIOS")
    print("="*70)
    
    for idx, usuario_data in enumerate(usuarios, 1):
        codloja = usuario_data['codloja']
        usuario = usuario_data['usuario']
        senha = usuario_data['senha']
        
        print(f"\n\n{'-'*70}")
        print(f"  USUÁRIO {idx}/{total_usuarios}")
        print(f"  Loja: {codloja}")
        print(f"  CPF/CNPJ: {usuario}")
        print(f"{'-'*70}")
        
        try:
            # Criar agente para este usuário
            print(f"\n→ Criando agente para loja {codloja}...")
            agent = NFSePlaywrightAgent(usuario, senha, codloja, download_dir)
            
            # Executar download
            agent.executar(dias_retroativos=dias_retroativos)
            
            # Aguardar antes do próximo usuário
            if idx < total_usuarios:
                print(f"\n✓ Usuário {idx}/{total_usuarios} processado!")
                print("→ Aguardando 5 segundos antes do próximo...")
                time.sleep(5)
            else:
                print(f"\n✓ Último usuário processado!")
                
        except Exception as e:
            print(f"\n✗ Erro ao processar usuário da loja {codloja}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "="*70)
    print(f"✓ TODOS OS {total_usuarios} USUÁRIOS FORAM PROCESSADOS")
    print("="*70)


def buscar_usuarios_oracle() -> List[dict]:
    """
    Busca usuários ativos no Oracle da tabela conf_munic_nfse
    
    Returns:
        Lista de dicionários com: codloja, usuario, senha
    """
    if not ORACLE_AVAILABLE:
        print("⚠️  Oracle não disponível")
        return []
    
    oracle_user = os.getenv("ORACLE_USER")
    oracle_password = os.getenv("ORACLE_PASSWORD")
    oracle_dsn = os.getenv("ORACLE_DSN")
    
    if not all([oracle_user, oracle_password, oracle_dsn]):
        print("⚠️  Configurações Oracle não encontradas")
        return []
    
    try:
        print("\n→ Buscando usuários no Oracle (CONF_MUNIC_NFSE)...")
        connection = oracledb.connect(
            user=oracle_user,
            password=oracle_password,
            dsn=oracle_dsn
        )
        
        cursor = connection.cursor()
        cursor.execute("""
            SELECT codloja, usuario, senha
            FROM CONF_MUNIC_NFSE
            WHERE INDSITUACAO = 'ATIVO'
            ORDER BY codloja
        """)
        
        usuarios = []
        for row in cursor:
            codloja = row[0]
            usuario = row[1]
            senha = row[2]
            
            if usuario and senha:
                usuarios.append({
                    'codloja': codloja,
                    'usuario': usuario,
                    'senha': senha
                })
                print(f"  ✓ Loja {codloja} - {usuario}")
            else:
                print(f"  ⚠️  Loja {codloja} - dados incompletos")
        
        cursor.close()
        connection.close()
        
        print(f"✓ Encontrados {len(usuarios)} usuários ativos")
        return usuarios
        
    except Exception as e:
        print(f"⚠️  Erro ao buscar usuários do Oracle: {e}")
        import traceback
        traceback.print_exc()
        return []




def main():
    """Função principal"""
    # Carregar configurações do .env
    dias_retroativos = int(os.getenv("DIAS_RETROATIVOS", "10"))
    download_dir = os.getenv("DIRETORIO_DOWNLOADS", "./downloads_nfse")
    
    print("\n" + "="*70)
    print("  CONFIGURAÇÃO")
    print("="*70)
    print(f"  Dias retroativos: {dias_retroativos}")
    print(f"  Diretório downloads: {download_dir}")
    print("="*70)
    
    # Buscar usuários do Oracle
    usuarios_oracle = buscar_usuarios_oracle()
    
    if not usuarios_oracle:
        print("\n✗ Nenhum usuário encontrado no Oracle")
        print("   Verifique a tabela CONF_MUNIC_NFSE")
        return
    
    print("\n" + "="*70)
    print(f"  Total de usuários: {len(usuarios_oracle)}")
    for idx, usuario_data in enumerate(usuarios_oracle, 1):
        print(f"    {idx}. Loja {usuario_data['codloja']} - {usuario_data['usuario']}")
    print("="*70)
    
    try:
        if len(usuarios_oracle) == 1:
            # Processar um único usuário
            usuario_data = usuarios_oracle[0]
            agent = NFSePlaywrightAgent(
                usuario_data['usuario'], 
                usuario_data['senha'], 
                usuario_data['codloja'],
                download_dir
            )
            agent.executar(dias_retroativos=dias_retroativos)
        else:
            # Processar múltiplos usuários
            processar_multiplos_usuarios(usuarios_oracle, download_dir, dias_retroativos)
    except Exception as e:
        print(f"\n✗ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()