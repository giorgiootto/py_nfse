"""
Script para importar arquivos XML/PDF da pasta downloads para Oracle
"""

import os
import socket
from pathlib import Path
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

try:
    import oracledb
except ImportError:
    print("✗ Erro: oracledb não instalado")
    print("  Instale com: pip install oracledb")
    exit(1)


class ImportadorOracle:
    """Importa arquivos XML/PDF para Oracle"""
    
    def __init__(self):
        self.oracle_user = os.getenv("ORACLE_USER")
        self.oracle_password = os.getenv("ORACLE_PASSWORD")
        self.oracle_dsn = os.getenv("ORACLE_DSN")
        self.download_dir = Path(os.getenv("DIRETORIO_DOWNLOADS", "./downloads"))
        
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
    
    def log(self, nivel: str, mensagem: str, chave: str = None):
        """Grava log no Oracle"""
        if not self.connection:
            return
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO ADM.log_processamento 
                (nivel, origem, mensagem, chave_documento, usuario)
                VALUES (:nivel, :origem, :mensagem, :chave, :usuario)
            """, {
                'nivel': nivel,
                'origem': 'IMPORTADOR',
                'mensagem': mensagem[:4000],
                'chave': chave,
                'usuario': self.usuario_log[:50]
            })
            self.connection.commit()
            cursor.close()
        except Exception as e:
            print(f"    ⚠️  Erro ao gravar log: {e}")
    
    def existe_chave(self, chave: str) -> bool:
        """Verifica se chave já existe"""
        if not self.connection:
            return False
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM down_nfse WHERE CHAVE = :chave
            """, {'chave': chave})
            result = cursor.fetchone()
            cursor.close()
            return result[0] > 0
        except Exception as e:
            print(f"    ⚠️  Erro ao verificar chave: {e}")
            self.log('ERROR', f"Erro verificar chave: {e}", chave)
            return False
    
    def gravar_nota(self, chave: str, xml_path: Path, pdf_path: Path) -> bool:
        """Grava nota no Oracle"""
        if not self.connection:
            return False
        
        try:
            # Verificar se já existe
            if self.existe_chave(chave):
                print(f"  ⊘ Já existe: {chave}")
                return False
            
            # Ler arquivos
            xml_content = None
            pdf_content = None
            
            if xml_path.exists():
                xml_content = xml_path.read_text(encoding='utf-8')
                print(f"    → XML lido: {xml_path.stat().st_size} bytes")
            else:
                print(f"    ⚠️  XML não encontrado: {xml_path.name}")
            
            if pdf_path.exists():
                pdf_content = pdf_path.read_bytes()
                print(f"    → PDF lido: {pdf_path.stat().st_size} bytes")
            else:
                print(f"    ⚠️  PDF não encontrado: {pdf_path.name}")
            
            if not xml_content and not pdf_content:
                print(f"  ✗ Nenhum arquivo encontrado para: {chave}")
                self.log('WARN', 'Nenhum arquivo disponível', chave)
                return False
            
            # Inserir
            cursor = self.connection.cursor()
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
            self.connection.commit()
            cursor.close()
            
            print(f"  ✓ Gravado: {chave}")
            self.log('INFO', 'NFSe importada com sucesso', chave)
            return True
            
        except Exception as e:
            print(f"  ✗ Erro ao gravar {chave}: {e}")
            self.log('ERROR', f"Erro ao gravar: {e}", chave)
            return False
    
    def importar_pasta(self):
        """Importa todos os arquivos da pasta"""
        print("\n" + "="*70)
        print("  IMPORTADOR DE ARQUIVOS PARA ORACLE")
        print("="*70)
        print(f"  Pasta: {self.download_dir}")
        print("="*70)
        
        if not self.download_dir.exists():
            print(f"\n✗ Pasta não encontrada: {self.download_dir}")
            return
        
        # Listar arquivos XML
        xml_files = list(self.download_dir.glob("*.xml"))
        
        if not xml_files:
            print("\n⚠️  Nenhum arquivo XML encontrado na pasta")
            return
        
        print(f"\n→ Encontrados {len(xml_files)} arquivos XML")
        
        # Conectar
        if not self.conectar():
            return
        
        # Processar cada arquivo
        total = len(xml_files)
        gravados = 0
        existentes = 0
        erros = 0
        
        print(f"\n→ Processando arquivos...\n")
        
        for idx, xml_path in enumerate(xml_files, 1):
            chave = xml_path.stem  # Nome do arquivo sem extensão
            pdf_path = xml_path.with_suffix('.pdf')
            
            print(f"[{idx}/{total}] {chave}")
            
            try:
                if self.existe_chave(chave):
                    existentes += 1
                elif self.gravar_nota(chave, xml_path, pdf_path):
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
        print(f"  Total de arquivos: {total}")
        print(f"  ✓ Gravados: {gravados}")
        print(f"  ⊘ Já existentes: {existentes}")
        print(f"  ✗ Erros: {erros}")
        print("="*70)
        
        self.log('INFO', f"Importação concluída: {gravados} gravados, {existentes} existentes, {erros} erros", None)
        
        # Desconectar
        self.desconectar()


def main():
    """Função principal"""
    try:
        importador = ImportadorOracle()
        importador.importar_pasta()
    except Exception as e:
        print(f"\n✗ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
