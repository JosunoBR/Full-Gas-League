import os
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

def get_brasilia_now():
    """Retorna a data/hora atual no fuso horário de Brasília (UTC-3)."""
    return datetime.utcnow() - timedelta(hours=3)


# ImportaÃ§Ãµes de models (lazy import para evitar circular imports)
# SÃ£o importadas dentro das funÃ§Ãµes que as usam

# Tabela 1: Grid PadrÃ£o (AtÃ© 20 Pilotos)
PONTUACAO_20 = {
    1: 35, 2: 30, 3: 27, 4: 24, 5: 22, 6: 20, 7: 18, 8: 16, 9: 14, 10: 12,
    11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1
}

# Tabela 2: Grid Cheio (AtÃ© 22 Pilotos) - Suavizada do P10 ao P22
PONTUACAO_22 = {
    1: 35, 2: 30, 3: 27, 4: 24, 5: 22, 6: 20, 7: 18, 8: 16, 9: 14, 10: 13,
    11: 12, 12: 11, 13: 10, 14: 9, 15: 8, 16: 7, 17: 6, 18: 5, 19: 4, 20: 3,
    21: 2, 22: 1
}

# Ordem de Carros para Lastro Invertido 2026 (P1 e P2 pegam o pior carro, etc.)
# Ordem baseada no Campeonato de Construtores 2026 (Do pior/11º ao melhor/1º):
# Cadillac (11º) -> Aston Martin (10º) -> Williams (9º) -> Audi (8º) -> Haas (7º) -> Alpine (6º) -> Racing Bulls (5º) -> Red Bull (4º) -> McLaren (3º) -> Ferrari (2º) -> Mercedes (1º)
ORDEM_CARROS = [
    'Cadillac', 'Cadillac',          # P1 e P2 (Pior Carro)
    'Aston Martin', 'Aston Martin',  # P3 e P4
    'Williams', 'Williams',          # P5 e P6
    'Audi', 'Audi',                  # P7 e P8
    'Haas', 'Haas',                  # P9 e P10
    'Alpine', 'Alpine',              # P11 e P12
    'Racing Bulls', 'Racing Bulls',  # P13 e P14
    'Red Bull', 'Red Bull',          # P15 e P16
    'McLaren', 'McLaren',            # P17 e P18
    'Ferrari', 'Ferrari',            # P19 e P20
    'Mercedes', 'Mercedes'           # P21 e P22 (Melhor Carro)
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
    # O YouTube bloqueia embeds gerados apenas com o ID do clip (exige o ID do vÃ­deo original).
    # Retornamos None para que o sistema exiba o botÃ£o de "Link Direto" em vez de um player com erro.
    if "youtube.com/clip/" in link:
        return None
            
    # Suporte para YouTube Shorts
    if "youtube.com/shorts/" in link:
        try:
            video_id = link.split('/shorts/')[1].split('?')[0]
            return f"https://www.youtube.com/embed/{video_id}"
        except:
            pass

    # Suporte para URLs de Embed jÃ¡ prontas (caso o usuÃ¡rio cole a URL do src do iframe conforme o tutorial)
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
            # Se for link do YouTube mas nÃ£o conseguimos extrair o ID (ex: canal, playlist, ou link invÃ¡lido)
            # Retornamos None para evitar que o iframe tente carregar a pÃ¡gina inteira do YT (que serÃ¡ bloqueada)
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
        
        # Formato: twitch.tv/username (Stream ao vivo - nÃ£o Ã© embedÃ¡vel em contexto fixa)
        return None

    # Retorna o link original para tentar carregar em iframe (ex: links diretos .mp4 ou outros sites)
    return link


# --- HELPERS DE PONTUAÃ‡ÃƒO E CÃLCULOS ---

def calcular_perda(veredito):
    """
    Calcula pontos perdidos por puniÃ§Ã£o (veredito do tribunal).
    Fonte Ãºnica de verdade para cÃ¡lculo de penalidades.
    
    Args:
        veredito: String com tipo de puniÃ§Ã£o ('LEVE', 'MEDIA', 'GRAVE')
    
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


# --- GRID HELPERS (NormalizaÃ§Ã£o e Matching) ---

def get_grid_name(obj):
    """
    Retorna o nome do grid de um objeto, normalizando grid_config.
    
    PadrÃ£o: Se o objeto tem grid_config_id filled e um atributo grid_config,
    usa grid_config.nome. Caso contrÃ¡rio, usa o campo grid (string).
    
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
    Verifica se um objeto (Race, Team, etc) pertence a um grid especÃ­fico.
    
    Suporta dois modos:
    - Se grid_ref Ã© int: compara estritamente com grid_id
    - Se grid_ref Ã© GridConfig: compara nome normalizado
    
    Args:
        obj: Objeto com atributos grid_id/grid/grid_config (Race, Team, etc)
        grid_ref: int (grid_id) ou GridConfig instance
    
    Returns:
        bool: True se o objeto pertence ao grid especificado
    """
    obj_grid_name = get_grid_name(obj)
    
    if isinstance(grid_ref, int):
        # grid_ref Ã© um ID
        if hasattr(obj, 'grid_id') and obj.grid_id == grid_ref:
            return True
        # Fallback: busca por nome (requer contexto de GridConfig)
        return False
    else:
        # grid_ref Ã© um GridConfig ou similar com atributo nome
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


# --- QUERY HELPERS (Consolidaï¿½ï¿½o de Queries Comuns) ---

def get_pilot_results_for_grid(pilot_id, grid_id, season_id):
    """Busca todos os resultados de corrida de um piloto em um grid/temporada especï¿½fico."""
    from app.models import RaceResult, Race
    
    return RaceResult.query.join(Race).filter(
        RaceResult.pilot_id == pilot_id,
        Race.season_id == season_id,
        Race.grid_id == grid_id
    ).order_by(Race.data_corrida).all()


def get_active_protests_for_pilot(pilot_id, grid_id=None):
    """Busca protestos concluï¿½dos (puniï¿½ï¿½es) de um piloto."""
    from app.models import Protesto
    
    query = Protesto.query.filter_by(acusado_id=pilot_id, status='CONCLUIDO')
    if grid_id is not None:
        query = query.filter_by(grid_id=grid_id)
    return query.all()


# --- UTILITÁRIOS DE TELEFONE E DDI INTERNACIONAL ---

DDI_OPTIONS = [
    # América do Sul e do Norte
    {'code': '+55', 'flag': '🇧🇷', 'name': 'Brasil (+55)'},
    {'code': '+52', 'flag': '🇲🇽', 'name': 'México (+52)'},
    {'code': '+1', 'flag': '🇺🇸', 'name': 'EUA / Canadá (+1)'},
    {'code': '+54', 'flag': '🇦🇷', 'name': 'Argentina (+54)'},
    {'code': '+56', 'flag': '🇨🇱', 'name': 'Chile (+56)'},
    {'code': '+57', 'flag': '🇨🇴', 'name': 'Colômbia (+57)'},
    {'code': '+598', 'flag': '🇺🇾', 'name': 'Uruguai (+598)'},
    {'code': '+595', 'flag': '🇵🇾', 'name': 'Paraguai (+595)'},
    {'code': '+51', 'flag': '🇵🇪', 'name': 'Peru (+51)'},
    {'code': '+58', 'flag': '🇻🇪', 'name': 'Venezuela (+58)'},

    # Europa
    {'code': '+351', 'flag': '🇵🇹', 'name': 'Portugal (+351)'},
    {'code': '+34', 'flag': '🇪🇸', 'name': 'Espanha (+34)'},
    {'code': '+44', 'flag': '🇬🇧', 'name': 'Reino Unido (+44)'},
    {'code': '+39', 'flag': '🇮🇹', 'name': 'Itália (+39)'},
    {'code': '+33', 'flag': '🇫🇷', 'name': 'França (+33)'},
    {'code': '+49', 'flag': '🇩🇪', 'name': 'Alemanha (+49)'},
    {'code': '+31', 'flag': '🇳🇱', 'name': 'Holanda (+31)'},
    {'code': '+32', 'flag': '🇧🇪', 'name': 'Bélgica (+32)'},
    {'code': '+41', 'flag': '🇨🇭', 'name': 'Suíça (+41)'},
    {'code': '+43', 'flag': '🇦🇹', 'name': 'Áustria (+43)'},
    {'code': '+353', 'flag': '🇮🇪', 'name': 'Irlanda (+353)'},
    {'code': '+46', 'flag': '🇸🇪', 'name': 'Suécia (+46)'},
    {'code': '+47', 'flag': '🇳🇴', 'name': 'Noruega (+47)'},
    {'code': '+45', 'flag': '🇩🇰', 'name': 'Dinamarca (+45)'},
    {'code': '+358', 'flag': '🇫🇮', 'name': 'Finlândia (+358)'},
    {'code': '+48', 'flag': '🇵🇱', 'name': 'Polônia (+48)'},
    {'code': '+420', 'flag': '🇨🇿', 'name': 'República Tcheca (+420)'},
    {'code': '+36', 'flag': '🇭🇺', 'name': 'Hungria (+36)'},
    {'code': '+30', 'flag': '🇬🇷', 'name': 'Grécia (+30)'},
    {'code': '+40', 'flag': '🇷🇴', 'name': 'Romênia (+40)'},
    {'code': '+385', 'flag': '🇭🇷', 'name': 'Croácia (+385)'},
]

def format_international_phone(ddi, number):
    """
    Combina e formata o DDI e o número de telefone local.
    Ex: ddi="+55", number="(11) 95164-2119" -> "+55 (11) 95164-2119"
    """
    if not number or not str(number).strip():
        return None

    num_clean = str(number).strip()
    if num_clean.startswith('+'):
        return num_clean[:30]

    ddi_clean = (ddi or '+55').strip()
    if not ddi_clean.startswith('+'):
        ddi_clean = '+' + ddi_clean

    return f"{ddi_clean} {num_clean}"[:30]

def parse_phone_components(telefone_str):
    """
    Extrai o DDI (ex: '+55') e o número local a partir da string armazenada.
    """
    if not telefone_str:
        return '+55', ''

    s = str(telefone_str).strip()
    if s.startswith('+'):
        parts = s.split(' ', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        
        for item in DDI_OPTIONS:
            c = item['code']
            if s.startswith(c) and len(s) > len(c):
                return c, s[len(c):]
        return s[:4], s[4:]

    return '+55', s