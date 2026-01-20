import re
from flask import current_app

PONTUACAO_NORMAL = {
    1: 35, 2: 30, 3: 27, 4: 24, 5: 22, 
    6: 20, 7: 18, 8: 16, 9: 14, 10: 12,
    11: 10, 12: 9, 13: 8, 14: 7, 15: 6,
    16: 5, 17: 4, 18: 3, 19: 2, 20: 1
}

ORDEM_CARROS = [
    "Sauber", "Sauber", "Haas", "Haas", "Alpine", "Alpine", 
    "Racing Bulls", "Racing Bulls", "Williams", "Williams", 
    "Aston Martin", "Aston Martin", "Ferrari", "Ferrari", 
    "Mercedes", "Mercedes", "Red Bull", "Red Bull", "McLaren", "McLaren"
]

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def get_embed_url(url):
    if not url: return None
    # Regex robusto para YouTube (Web, Mobile, Shorts, Links encurtados)
    yt_pattern = r'(?:https?:\/\/)?(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/|v\/)|youtu\.be\/)([\w-]{11})'
    match_yt = re.search(yt_pattern, url)
    if match_yt: return f'https://www.youtube.com/embed/{match_yt.group(1)}'
    
    drive_pattern = r'drive\.google\.com\/file\/d\/([-_\w]+)'
    match_drive = re.search(drive_pattern, url)
    if match_drive: return f'https://drive.google.com/file/d/{match_drive.group(1)}/preview'
        
    return None