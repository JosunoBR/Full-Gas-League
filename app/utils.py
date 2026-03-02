# -*- coding: utf-8 -*-
import os
from urllib.parse import urlparse, parse_qs

# Importações de models (lazy import para evitar circular imports)
# São importadas dentro das funções que as usam

# Tabela 1: Grid Padrão (Até 20 Pilotos)
PONTUACAO_20 = {
    1: 35, 2: 30, 3: 27, 4: 24, 5: 22, 6: 20, 7: 18, 8: 16, 9: 14, 10: 12,
    11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1
}

# Tabela 2: Grid Cheio (Até 22 Pilotos) - Suavizada do P10 ao P22
PONTUACAO_22 = {
    1: 35, 2: 30, 3: 27, 4: 24, 5: 22, 6: 20, 7: 18, 8: 16, 9: 14, 10: 13,
    11: 12, 12: 11, 13: 10, 14: 9, 15: 8, 16: 7, 17: 6, 18: 5, 19: 4, 20: 3,
    21: 2, 22: 1
}

# Ordem de Carros para Lastro Invertido (P1 e P2 pegam o pior carro, etc.)
# Regulamento: Sauber (Pior) -> ... -> McLaren (Melhor)
ORDEM_CARROS = [
    'Sauber', 'Sauber',             # P1 e P2
    'Haas', 'Haas',                 # P3 e P4
    'Alpine', 'Alpine',             # P5 e P6
    'Racing Bulls', 'Racing Bulls', # P7 e P8
    'Williams', 'Williams',         # P9 e P10
    'Aston Martin', 'Aston Martin', # P11 e P12
    'Ferrari', 'Ferrari',           # P13 e P14
    'Mercedes', 'Mercedes',         # P15 e P16
    'Red Bull', 'Red Bull',         # P17 e P18
    'McLaren', 'McLaren',           # P19 e P20
    'McLaren', 'McLaren'            # P21 e P22 (Extra)
]

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_embed_url(link):
    if not link: return None
    
    # Suporte para Google Drive (Transforma view em preview para funcionar no iframe)
    if "drive.google.com" in link and "/view" in link:
        return link.replace("/view", "/preview")

    # Suporte para YouTube Clips
    # O YouTube bloqueia embeds gerados apenas com o ID do clip (exige o ID do vídeo original).
    # Retornamos None para que o sistema exiba o botão de "Link Direto" em vez de um player com erro.
    if "youtube.com/clip/" in link:
        return None
            
    # Suporte para YouTube Shorts
    if "youtube.com/shorts/" in link:
        try:
            video_id = link.split('/shorts/')[1].split('?')[0]
            return f"https://www.youtube.com/embed/{video_id}"
        except:
            pass

    # Suporte para URLs de Embed já prontas (caso o usuário cole a URL do src do iframe conforme o tutorial)
    if "youtube.com/embed/" in link:
        return link

    if "youtube.com" in link or "youtu.be" in link:
        video_id = None
        if "youtu.be" in link:
            video_id = link.split('/')[-1].split('?')[0]
        elif "youtube.com" in link:
            query = urlparse(link).query
            params = parse_qs(query)
            if 'v' in params:
                video_id = params['v'][0]
        
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"
        else:
            # Se for link do YouTube mas não conseguimos extrair o ID (ex: canal, playlist, ou link inválido)
            # Retornamos None para evitar que o iframe tente carregar a página inteira do YT (que será bloqueada)
            return None
            
    # Suporte para Twitch
    elif "twitch.tv" in link:
        # Normaliza a URL (remove www, normaliza protocolo)
        link_normalized = link.replace("https://", "").replace("http://", "").replace("www.", "")
        
        # Formato: twitch.tv/videos/12345678 (VOD saved)
        if "/videos/" in link:
            try:
                video_id = link.split('/videos/')[1].split('?')[0].split('&')[0].strip()
                if video_id.isdigit():
                    return f"https://player.twitch.tv/?video={video_id}&parent=localhost&parent=fullgasleague.pythonanywhere.com&parent=www.fullgasleague.com.br&autoplay=false"
            except:
                pass
        
        # Formato: twitch.tv/username/clip/CLIPNAME (Clips - retorna None para mostrar link direto)
        if "/clip/" in link:
            return None
        
        # Formato: twitch.tv/username (Stream ao vivo - não é embedável em contexto fixa)
        return None

    # Retorna o link original para tentar carregar em iframe (ex: links diretos .mp4 ou outros sites)
    return link


# --- HELPERS DE PONTUAÇÃO E CÁLCULOS ---

def calcular_perda(veredito):
    """
    Calcula pontos perdidos por punição (veredito do tribunal).
    Fonte única de verdade para cálculo de penalidades.
    
    Args:
        veredito: String com tipo de punição ('LEVE', 'MEDIA', 'GRAVE')
    
    Returns:
        int: Pontos a serem descontados (0, 3, 5 ou 10)
    """
    if veredito == 'LEVE':
        return 3
    elif veredito == 'MEDIA':
        return 5
    elif veredito == 'GRAVE':
        return 10
    return 0


# --- GRID HELPERS (Normalização e Matching) ---

def get_grid_name(obj):
    """
    Retorna o nome do grid de um objeto, normalizando grid_config.
    
    Padrão: Se o objeto tem grid_config_id filled e um atributo grid_config,
    usa grid_config.nome. Caso contrário, usa o campo grid (string).
    
    Args:
        obj: Objeto com atributos grid_config ou grid (Race, Team, etc)
    
    Returns:
        str: Nome do grid normalizado
    """
    if hasattr(obj, 'grid_config') and obj.grid_config:
        return obj.grid_config.nome.strip().upper()
    elif hasattr(obj, 'grid') and obj.grid:
        return obj.grid.strip().upper()
    return ""


def grid_matches(obj, grid_ref):
    """
    Verifica se um objeto (Race, Team, etc) pertence a um grid específico.
    
    Suporta dois modos:
    - Se grid_ref é int: compara com grid_id, com fallback para nome
    - Se grid_ref é GridConfig: compara nome normalizado
    
    Args:
        obj: Objeto com atributos grid_id/grid/grid_config (Race, Team, etc)
        grid_ref: int (grid_id) ou GridConfig instance
    
    Returns:
        bool: True se o objeto pertence ao grid especificado
    """
    obj_grid_name = get_grid_name(obj)
    
    if isinstance(grid_ref, int):
        # grid_ref é um ID
        if hasattr(obj, 'grid_id') and obj.grid_id == grid_ref:
            return True
        # Fallback: busca por nome (requer contexto de GridConfig)
        return False
    else:
        # grid_ref é um GridConfig ou similar com atributo nome
        grid_ref_name = (grid_ref.nome if hasattr(grid_ref, 'nome') else str(grid_ref)).strip().upper()
        return obj_grid_name == grid_ref_name


def find_grid_config(nome_grid, grid_configs_list):
    """
    Busca um GridConfig em uma lista pelo nome normalizado (case-insensitive).
    
    Args:
        nome_grid: str - Nome do grid a buscar (qualquer case)
        grid_configs_list: list - Lista de GridConfig objects
    
    Returns:
        GridConfig or None: GridConfig encontrado ou None
    """
    if not nome_grid or not grid_configs_list:
        return None
    
    nome_normalizado = nome_grid.strip().upper()
    for config in grid_configs_list:
        if config.nome.strip().upper() == nome_normalizado:
            return config
    
    return None


# --- EVOLUÇÃO DE PONTOS E ESTATÍSTICAS ---

def gerar_evolucao_pontos(piloto_id, grid_id, season_id):
    """
    Gera dados de evolução acumulativa de pontos para um piloto em um grid específico.
    
    Args:
        piloto_id: int - ID do piloto
        grid_id: int - ID do grid
        season_id: int - ID da temporada
    
    Returns:
        list: Lista de dicts com: 
              {'gp': nome_gp, 'data': data, 'pontos_acumulados': float, 'pontos_corrida': float}
    """
    # Import late para evitar circular imports
    from app.models import Race, RaceResult, Protesto
    
    # Busca todas as corridas da temporada neste grid, ordenadas por data
    corridas = Race.query.filter_by(season_id=season_id, grid_id=grid_id, status='Concluida')\
        .order_by(Race.data_corrida).all()
    
    if not corridas:
        return []
    
    # Busca resultados do piloto
    resultados = RaceResult.query.filter_by(pilot_id=piloto_id).join(Race)\
        .filter(Race.season_id == season_id, Race.grid_id == grid_id)\
        .order_by(Race.data_corrida).all()
    
    # Cria dicionário para lookup rápido
    results_dict = {r.race_id: r for r in resultados}
    
    # Busca punições do piloto (usando 'etapa' em vez de 'race')
    punicoes = Protesto.query.filter_by(acusado_id=piloto_id, status='CONCLUIDO')\
        .join(Race, Protesto.etapa_id == Race.id)\
        .filter(Race.season_id == season_id, Race.grid_id == grid_id).all()
    punicoes_dict = {p.etapa_id: calcular_perda(p.veredito_final) for p in punicoes}
    
    evolucao = []
    pontos_acumulados = 0.0
    
    for corrida in corridas:
        resultado = results_dict.get(corrida.id)
        
        if resultado:
            # Piloto participou da corrida
            pontos_corrida = float(resultado.pontos_ganhos or 0)
            penalidade = punicoes_dict.get(corrida.id, 0)
            pontos_acumulados += (pontos_corrida - penalidade)
            
            evolucao.append({
                'gp': corrida.nome_gp,
                'data': corrida.data_corrida.strftime('%d/%m'),
                'pontos_acumulados': round(pontos_acumulados, 1),
                'pontos_corrida': round(pontos_corrida - penalidade, 1)
            })
    
    return evolucao

# --- QUERY HELPERS (Consolida��o de Queries Comuns) ---

def get_pilot_results_for_grid(pilot_id, grid_id, season_id):
    """Busca todos os resultados de corrida de um piloto em um grid/temporada espec�fico."""
    from app.models import RaceResult, Race
    
    return RaceResult.query.join(Race).filter(
        RaceResult.pilot_id == pilot_id,
        Race.season_id == season_id,
        Race.grid_id == grid_id
    ).order_by(Race.data_corrida).all()


def get_active_protests_for_pilot(pilot_id, grid_id=None):
    """Busca protestos conclu�dos (puni��es) de um piloto."""
    from app.models import Protesto
    
    query = Protesto.query.filter_by(acusado_id=pilot_id, status='CONCLUIDO')
    if grid_id is not None:
        query = query.filter_by(grid_id=grid_id)
    return query.all()


def get_quali_ban_status(pilot_id, grid_id):
    """Verifica se um piloto est� com ban de classifica��o por puni��o recente."""
    from app.models import Protesto, RaceResult, Race
    
    ultimo_p = Protesto.query.filter_by(
        acusado_id=pilot_id, grid_id=grid_id, status='CONCLUIDO'
    ).filter(Protesto.veredito_final.in_(['MEDIA', 'GRAVE'])
    ).order_by(Protesto.data_fechamento.desc()).first()
    
    if not ultimo_p:
        return False
    
    ultima_res = RaceResult.query.join(Race).filter(
        RaceResult.pilot_id == pilot_id, Race.grid_id == grid_id,
        Race.status == 'Concluida', RaceResult.ausencia == None
    ).order_by(Race.data_corrida.desc()).first()
    
    return not ultima_res or ultimo_p.data_fechamento.date() >= ultima_res.race.data_corrida
