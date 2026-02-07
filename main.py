import os
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import time


class TecnoSpeedNFSeAPI:
    """Cliente para API de Notas Tomadas da TecnoSpeed"""
    
    BASE_URL = "https://api.nfse.tecnospeed.com.br/v1"
    
    def __init__(self, token_sh: str, cpf_cnpj_software_house: str, 
                 cpf_cnpj_tomador: str, download_dir: str = "./downloads"):
        """
        Inicializa o cliente da API
        
        Args:
            token_sh: Token obtido no TecnoAccount
            cpf_cnpj_software_house: CPF/CNPJ da Software House
            cpf_cnpj_tomador: CPF/CNPJ do tomador das notas
            download_dir: Diretório para salvar os XMLs
        """
        self.token_sh = token_sh
        self.cpf_cnpj_software_house = cpf_cnpj_software_house
        self.cpf_cnpj_tomador = cpf_cnpj_tomador
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Headers padrão para todas as requisições
        self.headers = {
            "token_sh": self.token_sh,
            "cpfCnpjSoftwareHouse": self.cpf_cnpj_software_house,
            "cpfCnpjTomador": self.cpf_cnpj_tomador
        }
        
    def _print_response(self, response: requests.Response, title: str):
        """Imprime resposta formatada"""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
        print(f"Status: {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except:
            print(response.text)
        print('='*70)
        
    def consultar_cidades_homologadas(self, filtro: Optional[str] = None, mostrar_detalhes: bool = False) -> List[Dict]:
        """
        Passo 3: Consultar cidades homologadas
        
        Args:
            filtro: Filtro opcional para nome da cidade
            mostrar_detalhes: Se True, mostra requisitos detalhados de cada cidade
            
        Returns:
            Lista de cidades homologadas
        """
        print("\n→ Consultando cidades homologadas...")
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        response = requests.get(
            f"{self.BASE_URL}/cidades",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            cidades = data.get("resposta", [])
            
            if filtro:
                cidades = [c for c in cidades if filtro.upper() in c.get("nome", "").upper()]
            
            print(f"✓ {len(cidades)} cidades encontradas")
            
            if mostrar_detalhes and cidades:
                print(f"\n{'='*70}")
                print("  REQUISITOS POR CIDADE")
                print('='*70)
                for cidade in cidades[:10]:  # Mostrar primeiras 10
                    print(f"\n📍 {cidade.get('nome')} (IBGE: {cidade.get('codigoIbge')})")
                    print(f"   Padrão: {cidade.get('padrao')}")
                    print(f"   🔐 Certificado obrigatório: {'Sim' if cidade.get('certificado') else 'Não'}")
                    print(f"   👤 Login obrigatório: {'Sim' if cidade.get('login') else 'Não'}")
                    print(f"   🔑 Senha obrigatória: {'Sim' if cidade.get('senha') else 'Não'}")
                    print(f"   🏢 Prestador obrigatório: {'Sim' if cidade.get('prestadorObrigatorioTomadas') else 'Não'}")
                if len(cidades) > 10:
                    print(f"\n... e mais {len(cidades) - 10} cidades")
                print('='*70)
            
            return cidades
        else:
            print(f"✗ Erro ao consultar cidades: {response.status_code}")
            self._print_response(response, "ERRO")
            return []
    
    def obter_requisitos_cidade(self, codigo_ibge: str) -> Optional[Dict]:
        """
        Obtém os requisitos específicos de uma cidade
        
        Args:
            codigo_ibge: Código IBGE da cidade
            
        Returns:
            Dicionário com requisitos da cidade
        """
        cidades = self.consultar_cidades_homologadas()
        for cidade in cidades:
            if cidade.get('codigoIbge') == codigo_ibge:
                return {
                    'nome': cidade.get('nome'),
                    'certificado_obrigatorio': cidade.get('certificado', False),
                    'login_obrigatorio': cidade.get('login', False),
                    'senha_obrigatoria': cidade.get('senha', False),
                    'prestador_obrigatorio': cidade.get('prestadorObrigatorioTomadas', False),
                    'padrao': cidade.get('padrao'),
                    'tipo_comunicacao': cidade.get('tipoComunicacao')
                }
        return None
    
    def cadastrar_certificado(self, pfx_path: str, pfx_password: str) -> Optional[str]:
        """
        Passo 2: Cadastrar certificado digital
        
        Args:
            pfx_path: Caminho do arquivo .pfx
            pfx_password: Senha do certificado
            
        Returns:
            ID do certificado cadastrado
        """
        print("\n→ Cadastrando certificado...")
        
        headers = self.headers.copy()
        headers["Content-Type"] = "multipart/form-data"
        del headers["Content-Type"]  # Deixar o requests definir
        
        with open(pfx_path, 'rb') as f:
            files = {
                'arquivo': (Path(pfx_path).name, f, 'application/x-pkcs12')
            }
            data = {
                'senha': pfx_password
            }
            
            response = requests.post(
                f"{self.BASE_URL}/certificados",
                headers=headers,
                files=files,
                data=data
            )
        
        if response.status_code in [200, 201]:
            result = response.json()
            cert_id = result.get("resposta", {}).get("id")
            print(f"✓ Certificado cadastrado: {cert_id}")
            self._print_response(response, "CERTIFICADO CADASTRADO")
            return cert_id
        else:
            print(f"✗ Erro ao cadastrar certificado: {response.status_code}")
            self._print_response(response, "ERRO")
            return None
    
    def listar_certificados(self) -> List[Dict]:
        """
        Listar certificados cadastrados
        
        Returns:
            Lista de certificados
        """
        print("\n→ Consultando certificados cadastrados...")
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        
        response = requests.get(
            f"{self.BASE_URL}/certificados",
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            certificados = result.get("resposta", [])
            
            if certificados:
                print(f"✓ {len(certificados)} certificado(s) encontrado(s)")
                print(f"\n{'='*70}")
                print("  CERTIFICADOS CADASTRADOS")
                print('='*70)
                for cert in certificados:
                    print(f"\nID: {cert.get('id')}")
                    print(f"Nome: {cert.get('nome', 'N/A')}")
                    print(f"Vencimento: {cert.get('vencimento', 'N/A')}")
                print('='*70)
            else:
                print("⚠️  Nenhum certificado cadastrado")
                print("   Use a opção 2 do menu para cadastrar um certificado")
            
            return certificados
        else:
            print(f"✗ Erro ao listar certificados: {response.status_code}")
            self._print_response(response, "ERRO")
            return []
    
    def adicionar_consulta(self, codigo_cidade: str, 
                          prestador_cnpj: Optional[str] = None, 
                          prestador_im: Optional[str] = None,
5                          tomador_im: Optional[str] = None,
                          periodo_dias: int = 30,
                          login: Optional[str] = None,
                          senha: Optional[str] = None,
                          verificar_requisitos: bool = True) -> Optional[str]:
        """
        Passo 4: Adicionar uma consulta de notas TOMADAS
        
        Args:
            codigo_cidade: Código IBGE da cidade
            prestador_cnpj: CPF/CNPJ do PRESTADOR (quem emitiu as notas) - obrigatório dependendo do município
            prestador_im: Inscrição Municipal do PRESTADOR (quem emitiu as notas)
            tomador_im: Inscrição Municipal do TOMADOR/DESTINATÁRIO (quem recebeu as notas, seu CNPJ)
            periodo_dias: Período em dias para consulta (padrão: 30)
            login: Login do município (se necessário)
            senha: Senha do município (se necessária)
            verificar_requisitos: Se True, verifica requisitos do município antes
            
        Returns:
            Protocolo da consulta
            
        Note:
            - PRESTADOR = quem EMITIU as notas (prestou os serviços)
            - TOMADOR/DESTINATÁRIO = quem RECEBEU as notas (tomou os serviços, seu CNPJ)
            - A exigência do CNPJ do prestador varia por município!
            - Use obter_requisitos_cidade() para verificar.
        """
        print("\n→ Adicionando consulta de notas...")
        
        # Verificar requisitos da cidade
        if verificar_requisitos:
            requisitos = self.obter_requisitos_cidade(codigo_cidade)
            if requisitos:
                print(f"\n📋 Requisitos de {requisitos['nome']}:")
                print(f"   🏢 Prestador obrigatório: {'Sim' if requisitos['prestador_obrigatorio'] else 'Não'}")
                print(f"   🔐 Certificado obrigatório: {'Sim' if requisitos['certificado_obrigatorio'] else 'Não'}")
                print(f"   👤 Login obrigatório: {'Sim' if requisitos['login_obrigatorio'] else 'Não'}")
                
                # Verificar se prestador é obrigatório
                if requisitos['prestador_obrigatorio'] and not prestador_cnpj:
                    print(f"\n⚠️  ATENÇÃO: Este município EXIGE o CNPJ do prestador!")
                    return None
                
                # Verificar se certificado é obrigatório
                if requisitos['certificado_obrigatorio']:
                    certificados = self.listar_certificados()
                    if not certificados:
                        print(f"\n❌ ERRO: Este município EXIGE certificado cadastrado!")
                        print(f"   Use a opção 2 do menu para cadastrar seu certificado .pfx")
                        return None
                    else:
                        print(f"✓ Certificado cadastrado encontrado")
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        
        # Calcular período
        data_final = datetime.now()
        data_inicial = data_final - timedelta(days=periodo_dias)
        
        # Montar payload base
        payload = {
            "codigoCidade": codigo_cidade,
            "destinatario": {
                "cpfCnpj": self.cpf_cnpj_tomador
            },
            "periodo": {
                "inicial": data_inicial.strftime("%Y-%m-%d"),
                "final": data_final.strftime("%Y-%m-%d")
            }
        }
        
        # Adicionar prestador apenas se fornecido
        if prestador_cnpj:
            payload["prestador"] = {
                "cpfCnpj": prestador_cnpj
            }
            if prestador_im:
                payload["prestador"]["inscricaoMunicipal"] = prestador_im
        
        # Adicionar campos opcionais do tomador/destinatário
        if tomador_im:
            payload["destinatario"]["inscricaoMunicipal"] = tomador_im
        if login and senha:
            payload["destinatario"]["autenticacao"] = {
                "login": login,
                "senha": senha
            }
        
        response = requests.post(
            f"{self.BASE_URL}/tomadas",
            headers=headers,
            json=payload
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            protocolo = result.get("resposta", {}).get("protocolo")
            print(f"✓ Consulta adicionada. Protocolo: {protocolo}")
            print(f"  Período: {data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}")
            self._print_response(response, "CONSULTA ADICIONADA")
            return protocolo
        else:
            print(f"✗ Erro ao adicionar consulta: {response.status_code}")
            self._print_response(response, "ERRO")
            return None
    
    def consultar_protocolo(self, protocolo: str) -> Optional[Dict]:
        """
        Passo 5: Consultar status do protocolo
        
        Args:
            protocolo: Número do protocolo
            
        Returns:
            Dados do protocolo
        """
        print(f"\n→ Consultando protocolo {protocolo}...")
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        
        response = requests.get(
            f"{self.BASE_URL}/tomadas/{protocolo}",
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            resposta = result.get("resposta", {})
            situacao = resposta.get("situacao")
            total = resposta.get("totalDeNotas", 0)
            
            print(f"✓ Situação: {situacao}")
            print(f"  Total de notas: {total}")
            
            if situacao != "CONCLUIDO":
                self._print_response(response, "STATUS DO PROTOCOLO")
            
            return resposta
        else:
            print(f"✗ Erro ao consultar protocolo: {response.status_code}")
            self._print_response(response, "ERRO")
            return None
    
    def consultar_notas(self, protocolo: str, pagina: int = 1) -> Optional[Dict]:
        """
        Passo 6: Consultar todas as notas do protocolo
        
        Args:
            protocolo: Número do protocolo
            pagina: Número da página (paginação a cada 100 notas)
            
        Returns:
            Dados das notas
        """
        print(f"\n→ Consultando notas do protocolo (página {pagina})...")
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        
        params = {"pagina": pagina} if pagina > 1 else {}
        
        response = requests.get(
            f"{self.BASE_URL}/tomadas/{protocolo}/notas",
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            result = response.json()
            resposta = result.get("resposta", {})
            notas = resposta.get("notas", [])
            
            print(f"✓ {len(notas)} notas encontradas nesta página")
            return result
        else:
            print(f"✗ Erro ao consultar notas: {response.status_code}")
            self._print_response(response, "ERRO")
            return None
    
    def download_xml(self, protocolo: str, nota_id: str, nome_arquivo: Optional[str] = None) -> bool:
        """
        Baixar XML de uma nota específica
        
        Args:
            protocolo: Número do protocolo
            nota_id: ID da nota
            nome_arquivo: Nome do arquivo (opcional)
            
        Returns:
            True se sucesso
        """
        headers = self.headers.copy()
        
        response = requests.get(
            f"{self.BASE_URL}/tomadas/{protocolo}/notas/{nota_id}/xml",
            headers=headers
        )
        
        if response.status_code == 200:
            if not nome_arquivo:
                nome_arquivo = f"nota_{nota_id}.xml"
            
            filepath = self.download_dir / nome_arquivo
            filepath.write_text(response.text, encoding='utf-8')
            
            print(f"  ✓ XML salvo: {filepath.name}")
            return True
        else:
            print(f"  ✗ Erro ao baixar XML: {response.status_code}")
            return False
    
    def processar_consulta_completa(self, codigo_cidade: str, 
                                   prestador_cnpj: Optional[str] = None,
                                   prestador_im: Optional[str] = None,
                                   tomador_im: Optional[str] = None,
                                   periodo_dias: int = 30,
                                   login: Optional[str] = None,
                                   senha: Optional[str] = None,
                                   aguardar_conclusao: bool = True) -> Optional[List[Dict]]:
        """
        Processo completo: adicionar consulta, aguardar e baixar notas TOMADAS
        
        Args:
            codigo_cidade: Código IBGE da cidade
            prestador_cnpj: CPF/CNPJ do PRESTADOR (quem emitiu) - opcional dependendo do município
            prestador_im: Inscrição Municipal do PRESTADOR (quem emitiu)
            tomador_im: Inscrição Municipal do TOMADOR (seu CNPJ, quem recebeu)
            periodo_dias: Período em dias para consulta
            login: Login do município (se necessário)
            senha: Senha do município (se necessária)
            aguardar_conclusao: Se deve aguardar conclusão da consulta
            
        Returns:
            Lista de notas
            
        Note:
            - PRESTADOR = quem EMITIU as notas
            - TOMADOR = VOCÊ (quem recebeu as notas)
            - A exigência do CNPJ do prestador varia por município!
        """
        print("\n" + "="*70)
        print("  PROCESSO COMPLETO DE CONSULTA DE NOTAS TOMADAS")
        print("="*70)
        
        # Passo 4: Adicionar consulta
        protocolo = self.adicionar_consulta(
            codigo_cidade=codigo_cidade,
            prestador_cnpj=prestador_cnpj,
            prestador_im=prestador_im,
            tomador_im=tomador_im,
            periodo_dias=periodo_dias,
            login=login,
            senha=senha
        )
        
        if not protocolo:
            return None
        
        if not aguardar_conclusao:
            print(f"\n⚠️  Consulta adicionada. Consulte o protocolo mais tarde:")
            print(f"   Protocolo: {protocolo}")
            return None
        
        # Passo 5: Aguardar conclusão
        print("\n⏳ Aguardando processamento (verificando a cada 30s)...")
        print("   Obs: Pode levar até 1 hora ou mais dependendo do município")
        
        tentativas = 0
        max_tentativas = 120  # 1 hora (30s * 120)
        
        while tentativas < max_tentativas:
            time.sleep(30)
            tentativas += 1
            
            status = self.consultar_protocolo(protocolo)
            
            if not status:
                continue
            
            situacao = status.get("situacao")
            
            if situacao == "CONCLUIDO":
                print(f"\n✓ Processamento concluído!")
                break
            elif situacao == "ERRO":
                print(f"\n✗ Erro no processamento")
                return None
            else:
                print(f"  [{tentativas}] Ainda processando... (situação: {situacao})")
        
        if tentativas >= max_tentativas:
            print("\n⚠️  Timeout aguardando conclusão. Consulte o protocolo mais tarde.")
            return None
        
        # Passo 6: Consultar e baixar notas
        todas_notas = []
        pagina = 1
        
        while True:
            resultado = self.consultar_notas(protocolo, pagina)
            
            if not resultado:
                break
            
            resposta = resultado.get("resposta", {})
            notas = resposta.get("notas", [])
            
            if not notas:
                break
            
            todas_notas.extend(notas)
            
            # Baixar XMLs
            print(f"\n📥 Baixando XMLs da página {pagina}...")
            for nota in notas:
                nota_id = nota.get("id")
                numero_nota = nota.get("numero", nota_id)
                nome_arquivo = f"nota_{numero_nota}_{nota_id}.xml"
                self.download_xml(protocolo, nota_id, nome_arquivo)
            
            # Verificar se há próxima página
            acoes = resultado.get("acoes", {})
            if "proximaPagina" not in acoes:
                break
            
            pagina += 1
        
        print(f"\n{'='*70}")
        print(f"  PROCESSO CONCLUÍDO!")
        print(f"  Total de notas: {len(todas_notas)}")
        print(f"  XMLs salvos em: {self.download_dir}")
        print("="*70)
        
        return todas_notas


def main():
    """Função principal"""
    print("\n" + "="*70)
    print("  AGENTE NFSe - API TecnoSpeed")
    print("="*70 + "\n")
    
    # Configurações
    token_sh = input("Token TecnoAccount [c84d2f944b9f695eb65c10c7b7a1da8b]: ").strip() or "c84d2f944b9f695eb65c10c7b7a1da8b"
    cpf_cnpj_sh = input("CPF/CNPJ da Software House: ").strip()
    cpf_cnpj_tomador = input("CPF/CNPJ do Tomador: ").strip()
    
    # Criar cliente
    api = TecnoSpeedNFSeAPI(
        token_sh=token_sh,
        cpf_cnpj_software_house=cpf_cnpj_sh,
        cpf_cnpj_tomador=cpf_cnpj_tomador
    )
    
    # Menu
    while True:
        print("\n" + "="*70)
        print("  MENU")
        print("="*70)
        print("  1. Consultar cidades homologadas")
        print("  2. Cadastrar certificado")
        print("  3. Listar certificados cadastrados")
        print("  4. Adicionar consulta de notas")
        print("  5. Consultar protocolo")
        print("  6. Processo completo (adicionar + aguardar + baixar)")
        print("  0. Sair")
        print("="*70)
        
        opcao = input("\nEscolha uma opção: ").strip()
        
        if opcao == "1":
            filtro = input("Filtrar cidade (opcional): ").strip() or None
            ver_detalhes = input("Mostrar requisitos detalhados? (s/n) [n]: ").strip().lower() == 's'
            cidades = api.consultar_cidades_homologadas(filtro, mostrar_detalhes=ver_detalhes)
            
            if cidades and not ver_detalhes:
                print(f"\n{'='*70}")
                print(f"  CIDADES HOMOLOGADAS ({len(cidades)})")
                print('='*70)
                for i, cidade in enumerate(cidades[:20], 1):  # Mostrar primeiras 20
                    prestador_obrig = "🏢" if cidade.get('prestadorObrigatorioTomadas') else "  "
                    print(f"{i:3}. {prestador_obrig} {cidade.get('nome'):28} | IBGE: {cidade.get('codigoIbge')} | "
                          f"{cidade.get('padrao')}")
                if len(cidades) > 20:
                    print(f"\n... e mais {len(cidades) - 20} cidades")
                print(f"\n🏢 = Prestador obrigatório")
                print('='*70)
        
        elif opcao == "2":
            pfx_path = input("Caminho do arquivo .pfx: ").strip()
            pfx_password = input("Senha do certificado: ").strip()
            api.cadastrar_certificado(pfx_path, pfx_password)
        
        elif opcao == "3":
            api.listar_certificados()
        
        elif opcao == "4":
            codigo_cidade = input("Código IBGE da cidade: ").strip()
            
            # Verificar requisitos
            requisitos = api.obter_requisitos_cidade(codigo_cidade)
            if requisitos:
                print(f"\n📋 Requisitos de {requisitos['nome']}:")
                print(f"   🏢 Prestador obrigatório: {'Sim' if requisitos['prestador_obrigatorio'] else 'Não'}")
            
            print("\n💡 Lembre-se:")
            print("   PRESTADOR = quem EMITIU as notas contra você")
            print("   TOMADOR = VOCÊ (quem recebeu/tomou os serviços)\n")
            
            prestador_cnpj = input("CPF/CNPJ do Prestador (quem emitiu as notas): ").strip() or None
            prestador_im = input("Inscrição Municipal do Prestador (opcional): ").strip() or None
            tomador_im = input("Inscrição Municipal do Tomador/VOCÊ (opcional): ").strip() or None
            periodo = int(input("Período em dias [30]: ").strip() or "30")
            
            protocolo = api.adicionar_consulta(
                codigo_cidade=codigo_cidade,
                prestador_cnpj=prestador_cnpj,
                prestador_im=prestador_im,
                tomador_im=tomador_im,
                periodo_dias=periodo
            )
            
            if protocolo:
                print(f"\n💾 Protocolo salvo: {protocolo}")
                print("   Use a opção 5 para consultar o status")
        
        elif opcao == "5":
            protocolo = input("Número do protocolo: ").strip()
            status = api.consultar_protocolo(protocolo)
            
            if status and status.get("situacao") == "CONCLUIDO":
                ver_notas = input("\nDeseja ver as notas? (s/n): ").strip().lower()
                if ver_notas == 's':
                    api.consultar_notas(protocolo)
        
        elif opcao == "6":
            print("\n" + "="*70)
            print("  PROCESSO COMPLETO")
            print("="*70)
            codigo_cidade = input("Código IBGE da cidade: ").strip()
            
            # Verificar requisitos
            requisitos = api.obter_requisitos_cidade(codigo_cidade)
            if requisitos:
                print(f"\n📋 Requisitos de {requisitos['nome']}:")
                print(f"   🏢 Prestador obrigatório: {'Sim' if requisitos['prestador_obrigatorio'] else 'Não'}")
            
            print("\n💡 Lembre-se:")
            print("   PRESTADOR = quem EMITIU as notas contra você")
            print("   TOMADOR = VOCÊ (quem recebeu/tomou os serviços)\n")
            
            prestador_cnpj = input("CPF/CNPJ do Prestador (quem emitiu as notas): ").strip() or None
            prestador_im = input("Inscrição Municipal do Prestador (opcional): ").strip() or None
            tomador_im = input("Inscrição Municipal do Tomador/VOCÊ (opcional): ").strip() or None
            periodo = int(input("Período em dias [30]: ").strip() or "30")
            
            api.processar_consulta_completa(
                codigo_cidade=codigo_cidade,
                prestador_cnpj=prestador_cnpj,
                prestador_im=prestador_im,
                tomador_im=tomador_im,
                periodo_dias=periodo
            )
        
        elif opcao == "0":
            print("\n👋 Até logo!")
            break
        
        else:
            print("\n❌ Opção inválida!")


if __name__ == "__main__":
    main()
