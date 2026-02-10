"""
Script para importar planilha lojas.xlsx para tabela CONF_MUNIC_NFSE no Oracle
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

try:
    import pandas as pd
except ImportError:
    print("✗ Erro: pandas não instalado")
    print("  Instale com: pip install pandas openpyxl")
    exit(1)


class ImportadorLojas:
    """Importa lojas da planilha Excel para Oracle"""
    
    def __init__(self, arquivo_excel="lojas.xlsx"):
        self.oracle_user = os.getenv("ORACLE_USER")
        self.oracle_password = os.getenv("ORACLE_PASSWORD")
        self.oracle_dsn = os.getenv("ORACLE_DSN")
        self.arquivo_excel = Path(arquivo_excel)
        
        if not all([self.oracle_user, self.oracle_password, self.oracle_dsn]):
            raise ValueError("Configurações Oracle não encontradas no .env")
        
        if not self.arquivo_excel.exists():
            raise FileNotFoundError(f"Arquivo {self.arquivo_excel} não encontrado")
        
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
            
            print("✓ Conectado com sucesso!\n")
            return True
            
        except Exception as e:
            print(f"✗ Erro ao conectar: {e}\n")
            return False
    
    def desconectar(self):
        """Desconecta do Oracle"""
        if self.connection:
            self.connection.close()
            print("\n✓ Desconectado do Oracle")
    
    def ler_planilha(self):
        """Lê a planilha Excel"""
        try:
            print(f"→ Lendo planilha {self.arquivo_excel}...")
            
            # Primeiro, ler a planilha para ver o que tem
            df_raw = pd.read_excel(self.arquivo_excel, header=None)
            print(f"\n📋 Conteúdo bruto da planilha ({len(df_raw)} linhas):")
            print("-" * 80)
            print(df_raw.head(10).to_string())
            print("-" * 80)
            
            # Tentar detectar se tem cabeçalho na primeira linha
            primeira_linha = df_raw.iloc[0] if len(df_raw) > 0 else None
            tem_cabecalho = False
            
            if primeira_linha is not None:
                # Se a primeira célula não é número, provavelmente é cabeçalho
                try:
                    float(primeira_linha[0])
                except (ValueError, TypeError):
                    tem_cabecalho = True
                    print(f"\n⚠️  Detectado cabeçalho na primeira linha, pulando...")
            
            # Ler novamente com ou sem cabeçalho
            if tem_cabecalho:
                df = pd.read_excel(self.arquivo_excel, header=0)
                # Renomear as 3 primeiras colunas
                colunas = df.columns.tolist()
                if len(colunas) >= 3:
                    df = df.iloc[:, :3]  # Pegar apenas as 3 primeiras colunas
                    df.columns = ['codloja', 'usuario', 'senha']
                else:
                    print(f"✗ Erro: Planilha deve ter pelo menos 3 colunas")
                    return None
            else:
                # Sem cabeçalho, usar as 3 primeiras colunas
                df = df_raw.iloc[:, :3].copy()
                df.columns = ['codloja', 'usuario', 'senha']
            
            print(f"\n→ Processando dados...")
            print(f"  Total de linhas antes da limpeza: {len(df)}")
            
            # Filtrar linhas vazias
            df = df.dropna(how='all')
            print(f"  Após remover linhas vazias: {len(df)}")
            
            # Converter codloja para inteiro (remover decimais se houver)
            df['codloja'] = pd.to_numeric(df['codloja'], errors='coerce').fillna(0).astype(int)
            
            # Remover linhas onde codloja é 0 ou inválido
            df = df[df['codloja'] > 0]
            print(f"  Após validar codloja (inteiro > 0): {len(df)}")
            
            # Converter usuario e senha para string
            df['usuario'] = df['usuario'].astype(str).str.strip()
            df['senha'] = df['senha'].astype(str).str.strip()
            
            # Remover linhas onde usuario ou senha estão vazios
            df = df[(df['usuario'] != '') & (df['usuario'] != 'nan') & 
                   (df['senha'] != '') & (df['senha'] != 'nan')]
            print(f"  Após validar usuario e senha: {len(df)}")
            
            print(f"\n✓ Planilha lida: {len(df)} registros válidos")
            
            if len(df) > 0:
                print(f"\n📊 Primeiros registros válidos:")
                print("-" * 80)
                print(df.head(10).to_string(index=False))
                print("-" * 80)
            
            return df
            
        except Exception as e:
            print(f"✗ Erro ao ler planilha: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def importar_lojas(self, df):
        """Importa lojas para a tabela CONF_MUNIC_NFSE"""
        if df is None or len(df) == 0:
            print("✗ Nenhum registro para importar")
            return
        
        try:
            cursor = self.connection.cursor()
            
            # SQL de inserção - idconfmunic e dtaalteracao são gerados automaticamente
            sql = """
                INSERT INTO CONF_MUNIC_NFSE 
                (codloja, usuario, senha, indsituacao)
                VALUES (:codloja, :usuario, :senha, 'ATIVO')
            """
            
            total = len(df)
            sucesso = 0
            erros = 0
            
            print(f"→ Importando {total} registro(s)...\n")
            
            for idx, row in df.iterrows():
                try:
                    cursor.execute(sql, {
                        'codloja': int(row['codloja']),
                        'usuario': str(row['usuario']),
                        'senha': str(row['senha'])
                    })
                    sucesso += 1
                    print(f"  ✓ Loja {row['codloja']} - {row['usuario']}")
                    
                except Exception as e:
                    erros += 1
                    print(f"  ✗ Loja {row['codloja']} - Erro: {e}")
            
            # Commit das transações
            self.connection.commit()
            cursor.close()
            
            print(f"\n{'='*60}")
            print(f"RESUMO DA IMPORTAÇÃO")
            print(f"{'='*60}")
            print(f"Total de registros: {total}")
            print(f"Importados com sucesso: {sucesso}")
            print(f"Erros: {erros}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"✗ Erro geral na importação: {e}")
            if self.connection:
                self.connection.rollback()
    
    def executar(self):
        """Executa o processo completo de importação"""
        print("="*60)
        print("IMPORTAÇÃO DE LOJAS PARA CONF_MUNIC_NFSE")
        print("="*60)
        
        # Ler planilha
        df = self.ler_planilha()
        
        if df is None or len(df) == 0:
            print("✗ Processo cancelado: nenhum registro válido encontrado")
            return
        
        # Conectar ao Oracle
        if not self.conectar():
            return
        
        try:
            # Importar lojas
            self.importar_lojas(df)
        finally:
            # Sempre desconectar
            self.desconectar()


def main():
    """Função principal"""
    try:
        importador = ImportadorLojas("lojas.xlsx")
        importador.executar()
        
    except Exception as e:
        print(f"\n✗ Erro fatal: {e}")


if __name__ == "__main__":
    main()
