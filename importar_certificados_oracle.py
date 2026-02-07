"""
Script para importar certificados .pfx para Oracle
"""

import os
import socket
import subprocess
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

try:
    import oracledb
except ImportError:
    print("✗ Erro: oracledb não instalado")
    print("  Instale com: pip install oracledb")
    exit(1)


class ImportadorCertificados:
    """Importa certificados para Oracle"""
    
    def __init__(self):
        self.oracle_user = os.getenv("ORACLE_USER")
        self.oracle_password = os.getenv("ORACLE_PASSWORD")
        self.oracle_dsn = os.getenv("ORACLE_DSN")
        self.senha_certificado = os.getenv("SENHA_CERTIFICADO", "condor")
        self.cert_dir = Path("certificados")
        
        if not all([self.oracle_user, self.oracle_password, self.oracle_dsn]):
            raise ValueError("Configurações Oracle não encontradas no .env")
        
        # Informações da máquina
        self.machine_name = socket.gethostname()
        self.machine_ip = socket.gethostbyname(self.machine_name)
        self.usuario_log = f"{self.machine_name} ({self.machine_ip})"
        
        self.connection = None
    
    def conectar(self):
        """Conecta ao Oracle"""
        try:
            print(f"\n→ Conectando ao Oracle...")
            print(f"  User: {self.oracle_user}")
            print(f"  DSN: {self.oracle_dsn}")
            
            self.connection = oracledb.connect(
                user=self.oracle_user,
                password=self.oracle_password,
                dsn=self.oracle_dsn
            )
            print("✓ Conectado com sucesso")
            return True
        except Exception as e:
            print(f"✗ Erro ao conectar: {e}")
            return False
    
    def desconectar(self):
        """Desconecta do Oracle"""
        if self.connection:
            try:
                self.connection.close()
                print("\n✓ Conexão fechada")
            except:
                pass
    
    def extrair_info_certificado(self, pfx_path: Path) -> dict:
        """
        Extrai informações do certificado usando PowerShell
        
        Returns:
            Dict com Subject, CNPJ, NotAfter, etc
        """
        try:
            print(f"    → Extraindo informações...")
            
            ps_command = f"""
            $pwd = ConvertTo-SecureString -String '{self.senha_certificado}' -Force -AsPlainText
            $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2('{pfx_path.absolute()}', $pwd)
            
            # Extrair informações
            $subject = $cert.Subject
            $notAfter = $cert.NotAfter.ToString("dd/MM/yyyy")
            $thumbprint = $cert.Thumbprint
            
            # Extrair CN (Common Name)
            $cn = ""
            if ($subject -match 'CN=([^,]+)') {{
                $cn = $matches[1]
            }}
            
            # Extrair CNPJ/CPF (geralmente em serialNumber ou CN)
            $cnpj = ""
            if ($subject -match 'serialNumber=([0-9]+)') {{
                $cnpj = $matches[1]
            }} elseif ($subject -match ':([0-9]{{14}})') {{
                $cnpj = $matches[1]
            }}
            
            # Retornar JSON
            @{{
                Subject = $cn
                CNPJ = $cnpj
                NotAfter = $notAfter
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
                cert_info = json.loads(result.stdout.strip())
                print(f"    ✓ Certificado: {cert_info['Subject']}")
                print(f"      CNPJ: {cert_info.get('CNPJ', 'N/A')}")
                print(f"      Expira em: {cert_info['NotAfter']}")
                return cert_info
            else:
                print(f"    ⚠️  Erro ao extrair info: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"    ⚠️  Erro ao extrair info: {e}")
            return None
    
    def existe_certificado(self, arquivo: str) -> bool:
        """Verifica se certificado já existe"""
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM cert_down_nfse WHERE arquivo = :arquivo
            """, {'arquivo': arquivo})
            result = cursor.fetchone()
            cursor.close()
            return result[0] > 0
        except Exception as e:
            print(f"    ⚠️  Erro ao verificar certificado: {e}")
            return False
    
    def gravar_certificado(self, arquivo: str, pfx_path: Path, cert_info: dict) -> bool:
        """Grava certificado no Oracle"""
        if not self.connection:
            return False
        
        try:
            # Verificar se já existe
            if self.existe_certificado(arquivo):
                print(f"  ⊘ Já existe: {arquivo}")
                return False
            
            # Montar string de informações
            cnpj = cert_info.get('CNPJ', 'N/A')
            empresa = cert_info.get('Subject', 'N/A')
            expiracao = cert_info.get('NotAfter', 'N/A')
            
            info_str = f"Empresa: {empresa} | CNPJ: {cnpj} | Expira em: {expiracao}"
            
            # Ler conteúdo binário do arquivo .pfx
            conteudo_pfx = pfx_path.read_bytes()
            print(f"    → Arquivo lido: {len(conteudo_pfx)} bytes")
            
            # Inserir
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO cert_down_nfse 
                (arquivo, Info, INDSITUACAO, conteudo)
                VALUES (:arquivo, :info, :situacao, :conteudo)
            """, {
                'arquivo': arquivo,
                'info': info_str[:4000],  # Limitar a 4000 chars
                'situacao': 'ATIVO',
                'conteudo': conteudo_pfx
            })
            self.connection.commit()
            cursor.close()
            
            print(f"  ✓ Gravado: {arquivo}")
            return True
            
        except Exception as e:
            print(f"  ✗ Erro ao gravar {arquivo}: {e}")
            return False
    
    def importar_certificados(self):
        """Importa todos os certificados da pasta"""
        print("\n" + "="*70)
        print("  IMPORTADOR DE CERTIFICADOS PARA ORACLE")
        print("="*70)
        print(f"  Pasta: {self.cert_dir}")
        print("="*70)
        
        if not self.cert_dir.exists():
            print(f"\n✗ Pasta não encontrada: {self.cert_dir}")
            return
        
        # Listar arquivos .pfx
        pfx_files = list(self.cert_dir.glob("*.pfx"))
        
        if not pfx_files:
            print("\n⚠️  Nenhum arquivo .pfx encontrado na pasta")
            return
        
        print(f"\n→ Encontrados {len(pfx_files)} certificados")
        
        # Conectar
        if not self.conectar():
            return
        
        # Processar cada certificado
        total = len(pfx_files)
        gravados = 0
        existentes = 0
        erros = 0
        
        print(f"\n→ Processando certificados...\n")
        
        for idx, pfx_path in enumerate(pfx_files, 1):
            arquivo = pfx_path.name
            
            print(f"[{idx}/{total}] {arquivo}")
            
            try:
                # Extrair informações
                cert_info = self.extrair_info_certificado(pfx_path)
                
                if not cert_info:
                    print(f"  ✗ Não foi possível extrair informações")
                    erros += 1
                    continue
                
                # Gravar no banco
                if self.existe_certificado(arquivo):
                    existentes += 1
                elif self.gravar_certificado(arquivo, pfx_path, cert_info):
                    gravados += 1
                else:
                    erros += 1
                    
            except Exception as e:
                print(f"  ✗ Erro: {e}")
                erros += 1
        
        # Resumo
        print("\n" + "="*70)
        print("  RESUMO")
        print("="*70)
        print(f"  Total de certificados: {total}")
        print(f"  ✓ Gravados: {gravados}")
        print(f"  ⊘ Já existentes: {existentes}")
        print(f"  ✗ Erros: {erros}")
        print("="*70)
        
        # Desconectar
        self.desconectar()


def main():
    """Função principal"""
    try:
        importador = ImportadorCertificados()
        importador.importar_certificados()
    except Exception as e:
        print(f"\n✗ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
