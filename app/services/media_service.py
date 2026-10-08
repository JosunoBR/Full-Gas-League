import os
import io
from datetime import datetime
from PIL import Image, ImageFont, ImageDraw
from flask import current_app
from app.models import db, Season, GridConfig, Race
from app.services.team_context import build_team_context
from app.services.scoring_service import ScoringService


class MediaService:
    """
    Serviço responsável pela geração dinâmica de artes e peças visuais para transmissão e mídias sociais.
    """

    _slices_cache = None
    _bg_cache = None

    # Mapeamento canônico das 11 equipes suportadas na arte oficial 2026
    # Tupla: (nome_arquivo, (x1, y1, x2, y2)) do recorte original da fatia
    TEAM_DEFINITIONS = {
        'FERRARI': ('Card Ferrari.png', (142, 203, 862, 306)),
        'RED BULL': ('Card RedBull.png', (142, 307, 862, 409)),
        'MERCEDES': ('Card Mercedes.png', (142, 411, 862, 515)),
        'ASTON MARTIN': ('Card Aston Martin.png', (142, 515, 862, 617)),
        'RACING BULLS': ('Card Racing Bulls.png', (142, 621, 862, 723)),
        'MCLAREN': ('Card Mclaren.png', (142, 725, 862, 827)),
        'ALPINE': ('Card Alpine.png', (142, 830, 862, 932)),  # Recorte sem resíduo inferior
        'AUDI': ('Card Audi.png', (142, 934, 862, 1036)),
        'HAAS': ('Card Haas.png', (142, 1038, 862, 1140)),
        'WILLIAMS': ('Card Williams.png', (142, 1142, 862, 1244)),
        'CADILLAC': ('Card Cadillac.png', (142, 1248, 862, 1350)),
    }

    # Coordenadas verticais (y_start, y_end) dos 11 degraus na imagem de fundo 1080x1350
    SLOTS_Y = [
        (203, 306),
        (307, 409),
        (411, 515),
        (515, 617),
        (621, 723),
        (725, 827),
        (830, 932),
        (934, 1036),
        (1038, 1140),
        (1142, 1244),
        (1248, 1350)
    ]

    @classmethod
    def _get_assets_dir(cls):
        try:
            if current_app and getattr(current_app, 'static_folder', None):
                return os.path.join(current_app.static_folder, 'tabela')
        except RuntimeError:
            pass
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'tabela'))

    @classmethod
    def _load_card_slices(cls):
        """Carrega e armazena em cache na memória os recortes das 11 equipes."""
        if cls._slices_cache is not None:
            return cls._slices_cache

        assets_dir = cls._get_assets_dir()
        slices = {}
        for key, (filename, crop_box) in cls.TEAM_DEFINITIONS.items():
            img_path = os.path.join(assets_dir, filename)
            if os.path.exists(img_path):
                full_img = Image.open(img_path).convert('RGBA')
                slices[key] = full_img.crop(crop_box)
            else:
                slices[key] = None

        cls._slices_cache = slices
        return cls._slices_cache

    @classmethod
    def match_team_key(cls, team_name):
        """
        Normaliza e associa o nome da equipe cadastrado no banco a uma das 11 chaves canônicas.
        """
        norm = (team_name or '').strip().upper()
        if 'FERRARI' in norm:
            return 'FERRARI'
        if 'RED BULL' in norm or 'ORACLE' in norm:
            return 'RED BULL'
        if 'MERCEDES' in norm:
            return 'MERCEDES'
        if 'ASTON' in norm:
            return 'ASTON MARTIN'
        if 'RACING BULLS' in norm or 'CASH APP' in norm or ' RB' in norm or norm.startswith('RB'):
            return 'RACING BULLS'
        if 'MCLAREN' in norm:
            return 'MCLAREN'
        if 'ALPINE' in norm or 'BWT' in norm:
            return 'ALPINE'
        if 'AUDI' in norm:
            return 'AUDI'
        if 'HAAS' in norm:
            return 'HAAS'
        if 'WILLIAMS' in norm:
            return 'WILLIAMS'
        if 'CADILLAC' in norm:
            return 'CADILLAC'
        return None

    @classmethod
    def get_stage_subtitle(cls, season, grid_id):
        """
        Calcula o texto da etapa para o subtítulo do cartaz com base no calendário do grid.
        Padrão: 'POINTS BEFORE THE [NOME DO GP] [ANO]' ou 'FINAL STANDINGS [ANO]'.
        """
        races = Race.query.filter_by(season_id=season.id, grid_id=grid_id).order_by(Race.data_corrida).all()
        today = datetime.utcnow().date()
        next_race = None
        for r in races:
            if r.status != 'Concluida' and (not r.data_corrida or r.data_corrida >= today):
                next_race = r
                break

        season_year = str(season.data_inicio.year if getattr(season, 'data_inicio', None) else datetime.utcnow().year)

        if next_race:
            gp_name = (next_race.nome_gp or 'NEXT GP').strip().upper()
            return f"POINTS BEFORE THE {gp_name} {season_year}".strip()

        # Se todas as etapas foram concluídas
        return f"FINAL STANDINGS {season_year}".strip()

    @classmethod
    def generate_constructors_graphic(cls, season_id, grid_id, custom_subtitle=None):
        """
        Gera a imagem final (1080x1350) da tabela de construtores com as 11 equipes
        organizadas por pontuação, escrevendo a pontuação e etapa com a tipografia F1 oficial.

        Retorna:
            io.BytesIO com a imagem codificada em PNG.
        """
        season = db.session.get(Season, season_id)
        grid_cfg = db.session.get(GridConfig, grid_id)
        if not season or not grid_cfg:
            raise ValueError(f"Temporada {season_id} ou Grid {grid_id} não encontrados.")

        assets_dir = cls._get_assets_dir()
        bg_path = os.path.join(assets_dir, 'BACKGROUND.png')
        font_path = os.path.join(assets_dir, 'Formula1-Bold_web_0.ttf')

        if not os.path.exists(bg_path):
            raise FileNotFoundError(f"Arquivo de plano de fundo não encontrado em: {bg_path}")

        bg = Image.open(bg_path).convert('RGBA')

        # 1. Coleta e ordenação das equipes do grid
        team_ctx = build_team_context(season.id)
        raw_constructors = ScoringService.build_constructors_for_home(
            season.id, [grid_cfg], team_ctx["canonical_teams"], team_ctx["alias_ids_by_key"]
        )
        grid_constructors = raw_constructors.get(grid_cfg.id, [])

        # Lista de equipes com pontos ordenados decrescentes
        sorted_standings = sorted(grid_constructors, key=lambda x: x['pontos'], reverse=True)

        card_slices = cls._load_card_slices()

        used_keys = set()
        slots_data = []

        for item in sorted_standings:
            team_obj = item['equipe']
            team_name = team_obj.nome if hasattr(team_obj, 'nome') else str(team_obj)
            key = cls.match_team_key(team_name)
            if key and key in card_slices and card_slices[key] is not None and key not in used_keys:
                slots_data.append((key, item['pontos']))
                used_keys.add(key)

        # Se houver equipes não pontuadas que não vieram no retorno, completa até as 11 equipes
        for key in cls.TEAM_DEFINITIONS.keys():
            if key not in used_keys and len(slots_data) < len(cls.SLOTS_Y):
                slots_data.append((key, 0))
                used_keys.add(key)

        # 2. Cola os cards de cada equipe no slot correspondente
        for idx, (team_key, pts) in enumerate(slots_data[:len(cls.SLOTS_Y)]):
            y1, y2 = cls.SLOTS_Y[idx]
            slice_img = card_slices.get(team_key)
            if not slice_img:
                continue

            target_height = y2 - y1
            if slice_img.height != target_height:
                slice_img = slice_img.resize((720, target_height), Image.Resampling.LANCZOS)

            bg.paste(slice_img, (142, y1), slice_img)

        # 3. Renderiza textos (subtítulo e pontos) com a fonte oficial
        draw = ImageDraw.Draw(bg)

        font_points = ImageFont.truetype(font_path, 44) if os.path.exists(font_path) else ImageFont.load_default()
        font_sub = ImageFont.truetype(font_path, 23) if os.path.exists(font_path) else ImageFont.load_default()

        # Subtítulo da etapa
        sub_text = custom_subtitle or cls.get_stage_subtitle(season, grid_id)
        draw.text((540, 138), sub_text, font=font_sub, fill=(255, 255, 255), anchor='mm')

        # Pontuações na coluna vermelha (centro X = 971)
        for idx, (team_key, pts) in enumerate(slots_data[:len(cls.SLOTS_Y)]):
            y1, y2 = cls.SLOTS_Y[idx]
            center_y = (y1 + y2) / 2

            if isinstance(pts, (int, float)) and float(pts).is_integer():
                pts_str = str(int(pts))
            else:
                pts_str = f"{pts:g}"

            draw.text((971, center_y), pts_str, font=font_points, fill=(255, 255, 255), anchor='mm')

        # 4. Salva o resultado final em buffer de memória
        output_buffer = io.BytesIO()
        bg.save(output_buffer, format='PNG', optimize=True)
        output_buffer.seek(0)
        return output_buffer
