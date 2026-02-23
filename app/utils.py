import os
from urllib.parse import urlparse, parse_qs

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
    if "youtube.com/clip/" in link:
        try:
            clip_id = link.split('/clip/')[1].split('?')[0]
            return f"https://www.youtube.com/embed/clip/{clip_id}"
        except:
            pass
            
    # Suporte para YouTube Shorts
    if "youtube.com/shorts/" in link:
        try:
            video_id = link.split('/shorts/')[1].split('?')[0]
            return f"https://www.youtube.com/embed/{video_id}"
        except:
            pass

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
    elif "twitch.tv" in link:
        # Exemplo: https://www.twitch.tv/videos/12345678
        parts = link.split('/')
        if 'videos' in parts:
            video_id = parts[parts.index('videos') + 1]
            return f"https://player.twitch.tv/?video={video_id}&parent=localhost&parent=fullgasleague.pythonanywhere.com&parent=www.fullgasleague.com.br&autoplay=false"

    # Retorna o link original para tentar carregar em iframe (ex: links diretos .mp4 ou outros sites)
    return link