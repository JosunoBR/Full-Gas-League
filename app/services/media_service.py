import os
import io
from datetime import datetime
from PIL import Image, ImageFont, ImageDraw
from flask import current_app
from app.models import db, Season, GridConfig, Race, PilotProfile, User, Team, Protesto
from app.utils import grid_matches
from app.services.team_context import build_team_context
from app.services.scoring_service import ScoringService


class MediaService:
    """
    Serviço responsável pela geração dinâmica de artes e peças visuais para transmissão e mídias sociais.
    """

    _slices_cache = None
    _slices_mtime = 0
    _pilot_cards_cache = None
    _pilot_cards_mtime = 0
    _bg_cache = None

    # Mapeamento canônico das 11 equipes suportadas na arte oficial 2026 (Construtores)
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

    # Cards individuais oficiais de pilotos por equipe
    PILOT_CARD_DEFINITIONS = {
        'FERRARI': 'card_piloto_ferrari.png',
        'RED BULL': 'card_piloto_redbull.png',
        'MERCEDES': 'card_piloto_mercedes.png',
        'ASTON MARTIN': 'card_piloto_aston.png',
        'RACING BULLS': 'card_piloto_racingbulls.png',
        'MCLAREN': 'card_piloto_mclaren.png',
        'ALPINE': 'card_piloto_alpine.png',
        'AUDI': 'card_piloto_audi.png',
        'HAAS': 'card_piloto_haas.png',
        'WILLIAMS': 'card_piloto_williams.png',
        'CADILLAC': 'card_piloto_cadillac.png',
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
        """Carrega e armazena em cache na memória os recortes das 11 equipes (Construtores) com recarregamento automático ao modificar arquivos."""
        assets_dir = cls._get_assets_dir()

        # Monitora a data de modificação mais recente dos arquivos de construtores
        current_mtime = 0
        for filename, _ in cls.TEAM_DEFINITIONS.values():
            img_path = os.path.join(assets_dir, filename)
            if os.path.exists(img_path):
                current_mtime = max(current_mtime, os.path.getmtime(img_path))

        if cls._slices_cache is not None and cls._slices_mtime == current_mtime:
            return cls._slices_cache

        slices = {}
        for key, (filename, crop_box) in cls.TEAM_DEFINITIONS.items():
            img_path = os.path.join(assets_dir, filename)
            if os.path.exists(img_path):
                full_img = Image.open(img_path).convert('RGBA')
                # Se a imagem já for um card individual recortado (largura ~720 e altura ~102)
                if full_img.width <= 850 and full_img.height <= 250:
                    slices[key] = full_img
                else:
                    slices[key] = full_img.crop(crop_box)
            else:
                slices[key] = None

        cls._slices_cache = slices
        cls._slices_mtime = current_mtime
        return cls._slices_cache

    @classmethod
    def _load_pilot_cards(cls):
        """Carrega e armazena em cache na memória os cards oficiais individuais de pilotos com recarregamento automático ao modificar arquivos."""
        assets_dir = cls._get_assets_dir()

        # Monitora a data de modificação mais recente dos arquivos de pilotos
        current_mtime = 0
        for filename in cls.PILOT_CARD_DEFINITIONS.values():
            img_path = os.path.join(assets_dir, filename)
            if os.path.exists(img_path):
                current_mtime = max(current_mtime, os.path.getmtime(img_path))

        if cls._pilot_cards_cache is not None and cls._pilot_cards_mtime == current_mtime:
            return cls._pilot_cards_cache

        cards = {}
        for key, filename in cls.PILOT_CARD_DEFINITIONS.items():
            img_path = os.path.join(assets_dir, filename)
            if os.path.exists(img_path):
                cards[key] = Image.open(img_path).convert('RGBA')
            else:
                cards[key] = None

        cls._pilot_cards_cache = cards
        cls._pilot_cards_mtime = current_mtime
        return cls._pilot_cards_cache

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
    def get_drivers_stage_subtitle(cls, season, grid_id):
        """
        Gera o subtítulo em português no padrão oficial da imagem de referência:
        Ex: 'TABELA APÓS ETAPA 5 - GP DO AZERBAIJÃO' ou 'TABELA OFICIAL DE PILOTOS [ANO]'.
        """
        races = Race.query.filter_by(season_id=season.id, grid_id=grid_id).order_by(Race.data_corrida, Race.id).all()
        completed_races = [r for r in races if r.status == 'Concluida']

        if completed_races:
            last = completed_races[-1]
            etapa_idx = len(completed_races)
            gp_name = (last.nome_gp or 'GRANDE PRÊMIO').strip().upper()
            return f"TABELA APÓS ETAPA {etapa_idx} - {gp_name}"

        if races:
            first = races[0]
            gp_name = (first.nome_gp or 'GRANDE PRÊMIO').strip().upper()
            return f"TABELA ANTES DA ETAPA 1 - {gp_name}"

        season_year = str(season.data_inicio.year if getattr(season, 'data_inicio', None) else datetime.utcnow().year)
        return f"TABELA OFICIAL DE PILOTOS {season_year}"

    @classmethod
    def get_grid_drivers_media_data(cls, season, grid_cfg):
        """
        Constrói a classificação consolidada dos pilotos com pontuação oficial via ScoringService,
        equipe resolvida e ordenação decrescente por pontos, vitórias e pódios.
        """
        punicoes_temporada = Protesto.query.join(Race).filter(
            Protesto.status == 'CONCLUIDO',
            Race.season_id == season.id
        ).all()

        punicoes_by_pilot = {}
        for prot in punicoes_temporada:
            if prot.acusado_id not in punicoes_by_pilot:
                punicoes_by_pilot[prot.acusado_id] = []
            punicoes_by_pilot[prot.acusado_id].append(prot)

        pilotos = PilotProfile.query.join(User).all()
        all_season_teams = Team.query.filter_by(season_id=season.id).all()

        classificacao = []
        g_id = grid_cfg.id

        for p in pilotos:
            resultados_season = [r for r in p.race_results if r.race.season_id == season.id]
            grids_participados_ids = set()
            teams_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.pilots)]
            reserves_season = [t for t in all_season_teams if any(pilot.id == p.id for pilot in t.reserves)]

            if p.grid and p.grid != 'SEM_GRID':
                grid_tokens = [token.strip() for token in p.grid.split(',') if token.strip().isdigit()]
                grids_participados_ids.update(int(token) for token in grid_tokens)
            for t in (teams_season + reserves_season):
                if t.grid_id:
                    grids_participados_ids.add(t.grid_id)

            if g_id not in grids_participados_ids:
                continue

            res_no_grid = [r for r in resultados_season if grid_matches(r.race, grid_cfg)]
            my_punicoes = punicoes_by_pilot.get(p.id, [])
            my_punicoes_grid = [pun for pun in my_punicoes if pun.grid_id == g_id]

            pontos_totais = ScoringService.calculate_pilot_total_points(p.id, season.id, g_id)
            vitorias = sum(1 for r in res_no_grid if r.posicao == 1 and not r.dsq)
            podios = sum(1 for r in res_no_grid if r.posicao in [1, 2, 3] and not r.dsq)

            is_reserve = False
            is_titular = any(t.grid_id == g_id for t in teams_season)
            if not is_titular:
                is_reserve = any(t.grid_id == g_id for t in reserves_season)

            team_obj = next((t for t in teams_season if t.grid_id == g_id), None)
            if not team_obj:
                team_obj = next((t for t in reserves_season if t.grid_id == g_id), None)
            if not team_obj:
                sorted_res = sorted(
                    res_no_grid,
                    key=lambda x: (x.race.data_corrida or datetime.min.date(), x.id or 0),
                    reverse=True
                )
                for r in sorted_res:
                    if r.team_snapshot:
                        team_obj = r.team_snapshot
                        break

            team_name = team_obj.nome.strip() if team_obj else '-'

            info = {
                'piloto': p,
                'nome_real': (p.nome_real or '').strip(),
                'nickname': (p.nickname or '').strip(),
                'team': team_name,
                'team_key': cls.match_team_key(team_name),
                'pontos': pontos_totais,
                'vitorias': vitorias,
                'podios': podios,
                'cnh': p.pontos_cnh,
                'advertencias': p.advertencias_acumuladas,
                'punicoes': my_punicoes_grid,
                'is_reserve': is_reserve
            }
            if not any(x['piloto'].id == p.id for x in classificacao):
                classificacao.append(info)

        classificacao.sort(key=lambda x: (x['pontos'], x['vitorias'], x['podios']), reverse=True)
        disciplina = list(classificacao)
        disciplina.sort(key=lambda x: x['cnh'])

        return {
            'classificacao': classificacao,
            'disciplina': disciplina
        }

    @classmethod
    def _get_pilot_photo(cls, pilot, target_size=(110, 102)):
        """
        Carrega e ajusta a foto do piloto para renderização no card.
        Suporta fotos transparentes (PNG cutout) e fotos comuns (com máscara arredondada).
        Fallback para NP.jpg em caso de ausência.
        """
        assets_dir = cls._get_assets_dir()
        uploads_dir = None
        np_path = None
        try:
            if current_app and getattr(current_app, 'static_folder', None):
                uploads_dir = os.path.join(current_app.static_folder, 'uploads')
                np_path = os.path.join(current_app.static_folder, 'img', 'NP.jpg')
        except RuntimeError:
            pass

        if not uploads_dir:
            uploads_dir = os.path.abspath(os.path.join(assets_dir, '..', 'uploads'))
        if not np_path:
            np_path = os.path.abspath(os.path.join(assets_dir, '..', 'img', 'NP.jpg'))

        photo_img = None
        if pilot and getattr(pilot, 'foto_url', None):
            fpath = os.path.join(uploads_dir, pilot.foto_url)
            if os.path.exists(fpath):
                try:
                    photo_img = Image.open(fpath).convert('RGBA')
                except Exception:
                    photo_img = None

        is_np = False
        if photo_img is None and os.path.exists(np_path):
            try:
                photo_img = Image.open(np_path).convert('RGBA')
                is_np = True
            except Exception:
                photo_img = None

        if photo_img is None:
            return None

        # Se for o fallback NP.jpg, remove o fundo branco do estúdio para integrar perfeitamente ao card
        if is_np:
            try:
                datas = photo_img.getdata()
                new_data = []
                for item in datas:
                    if item[0] > 230 and item[1] > 230 and item[2] > 230:
                        new_data.append((255, 255, 255, 0))
                    else:
                        new_data.append(item)
                photo_img.putdata(new_data)
            except Exception:
                pass

        target_w, target_h = target_size

        # Verifica se a imagem tem canal alfa com transparência real (silhueta/cutout)
        has_transparency = False
        try:
            alpha = photo_img.split()[3]
            min_alpha, max_alpha = alpha.getextrema()
            has_transparency = min_alpha < 240
        except Exception:
            has_transparency = False

        if has_transparency:
            # Silhueta de busto transparente: escala baseada na altura com leve sobreposição
            render_h = target_h + 4
            ratio = render_h / float(photo_img.height)
            render_w = max(1, int(photo_img.width * ratio))
            if render_w > 130:
                render_w = 130
                render_h = max(1, int(photo_img.height * (130.0 / photo_img.width)))
            resized = photo_img.resize((render_w, render_h), Image.Resampling.LANCZOS)
            return resized, True
        else:
            # Foto comum (JPG ou sem recorte): enquadramento de busto com bordas arredondadas suaves
            box_w = 88
            box_h = target_h - 10
            scale = max(box_w / float(photo_img.width), box_h / float(photo_img.height))
            nw = max(1, int(photo_img.width * scale))
            nh = max(1, int(photo_img.height * scale))
            scaled = photo_img.resize((nw, nh), Image.Resampling.LANCZOS)
            left = (nw - box_w) // 2
            top = max(0, (nh - box_h) // 3)
            cropped = scaled.crop((left, top, left + box_w, top + box_h))

            mask = Image.new('L', (box_w, box_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([(0, 0), (box_w, box_h)], radius=12, fill=255)
            cropped.putalpha(mask)
            return cropped, False

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
            if slice_img.size != (720, target_height):
                slice_img = slice_img.resize((720, target_height), Image.Resampling.LANCZOS)

            bg.paste(slice_img, (142, y1), slice_img)

        # 3. Renderiza textos (subtítulo e pontos) com a fonte oficial
        draw = ImageDraw.Draw(bg)

        font_points = ImageFont.truetype(font_path, 44) if os.path.exists(font_path) else ImageFont.load_default()
        font_sub = ImageFont.truetype(font_path, 23) if os.path.exists(font_path) else ImageFont.load_default()

        sub_text = custom_subtitle or cls.get_stage_subtitle(season, grid_id)
        draw.text((540, 138), sub_text, font=font_sub, fill=(255, 255, 255), anchor='mm')

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

    @classmethod
    def generate_drivers_graphic(cls, season_id, grid_id, pilot_type='titulares', custom_subtitle=None):
        """
        Gera a imagem oficial (1080x1350) da Tabela de Pilotos (Top 10) baseada fielmente
        na arte oficial (Imagem 1 de referência):
        - Fundo oficial BACKGROUND.png com as faixas vermelhas e logo
        - Título 'TABELA DE PILOTOS' em fonte Formula 1
        - Números de 1 a 10 no painel vermelho à esquerda
        - Card correspondente à equipe do piloto
        - Foto/silhueta do piloto afastada do logotipo da equipe (centro X ~ 375)
        - Exibição de apenas os 2 primeiros nomes em caixa alta e negrito
        - ID/Nickname do piloto menor, logo abaixo
        - Pontuação oficial na coluna vermelha à direita
        - Rodapé inferior em preto com 'TABELA APÓS ETAPA X - GP...'

        Retorna:
            io.BytesIO com a imagem codificada em PNG.
        """
        season = db.session.get(Season, season_id)
        grid_cfg = db.session.get(GridConfig, grid_id)
        if not season or not grid_cfg:
            raise ValueError(f"Temporada {season_id} ou Grid {grid_id} não encontrados.")

        assets_dir = cls._get_assets_dir()
        bg_path = os.path.join(assets_dir, 'BACKGROUND.png')
        font_wide_path = os.path.join(assets_dir, 'Formula1-Wide_web_0.ttf')
        font_bold_path = os.path.join(assets_dir, 'Formula1-Bold_web_0.ttf')
        font_reg_path = os.path.join(assets_dir, 'Formula1-Regular_web_0.ttf')

        if not os.path.exists(bg_path):
            raise FileNotFoundError(f"Arquivo de plano de fundo não encontrado em: {bg_path}")

        bg = Image.open(bg_path).convert('RGBA')

        # 1. Obtém e filtra os pilotos classificados para o Grid (Top 11 - preenchendo todos os 11 slots do background)
        media_data = cls.get_grid_drivers_media_data(season, grid_cfg)
        all_pilots = media_data.get('classificacao', [])

        if pilot_type == 'reservas':
            filtered_pilots = [p for p in all_pilots if p.get('is_reserve')]
        else:
            filtered_pilots = [p for p in all_pilots if not p.get('is_reserve')]

        top_11 = filtered_pilots[:len(cls.SLOTS_Y)]

        # 2. Carrega os cards de equipes de pilotos
        pilot_cards = cls._load_pilot_cards()

        # 3. Desenha cada um dos até 11 slots
        # Posição centralizada da foto do piloto (X = 408 para afastar completamente do logotipo da McLaren e outras equipes)
        photo_center_x = 408

        for idx in range(min(len(cls.SLOTS_Y), len(top_11))):
            item = top_11[idx]
            y1, y2 = cls.SLOTS_Y[idx]
            target_height = y2 - y1

            team_key = item.get('team_key') or cls.match_team_key(item.get('team'))
            card_img = pilot_cards.get(team_key) if team_key else None

            # Fallback se a equipe não tiver card mapeado
            if not card_img:
                for k, c in pilot_cards.items():
                    if c is not None:
                        card_img = c
                        break

            if card_img:
                card_resized = card_img.resize((720, target_height), Image.Resampling.LANCZOS)
                bg.paste(card_resized, (142, y1), card_resized)

            # Foto do piloto (centralizada na área X ~ 408 sem sobrepor nenhum logotipo)
            pilot_obj = item.get('piloto')
            photo_info = cls._get_pilot_photo(pilot_obj, (110, target_height))
            if photo_info:
                photo_render, is_cutout = photo_info
                if is_cutout:
                    px = int(photo_center_x - photo_render.width / 2)
                    py = y2 - photo_render.height
                    bg.paste(photo_render, (px, py), photo_render)
                else:
                    px = int(photo_center_x - photo_render.width / 2)
                    py = y1 + 5
                    bg.paste(photo_render, (px, py), photo_render)

        # 4. Renderiza Textos: Título, Subtítulo, Nomes, IDs e Pontos
        draw = ImageDraw.Draw(bg)

        # Fontes Oficiais Padronizadas (Tamanhos fixos e universais para todas as temporadas e grids)
        font_title = ImageFont.truetype(font_wide_path, 42) if os.path.exists(font_wide_path) else (
            ImageFont.truetype(font_bold_path, 42) if os.path.exists(font_bold_path) else ImageFont.load_default()
        )
        font_sub = ImageFont.truetype(font_bold_path, 21) if os.path.exists(font_bold_path) else ImageFont.load_default()
        font_name = ImageFont.truetype(font_bold_path, 25) if os.path.exists(font_bold_path) else ImageFont.load_default()
        font_id_file = font_reg_path if os.path.exists(font_reg_path) else font_bold_path
        font_id = ImageFont.truetype(font_id_file, 18) if os.path.exists(font_id_file) else ImageFont.load_default()
        font_points = ImageFont.truetype(font_bold_path, 46) if os.path.exists(font_bold_path) else ImageFont.load_default()

        # A. Título Superior 'TABELA DE PILOTOS' e Subtítulo da Etapa no Topo
        draw.text((540, 114), "TABELA DE PILOTOS", font=font_title, fill=(255, 255, 255), anchor='mm')
        sub_text = custom_subtitle or cls.get_drivers_stage_subtitle(season, grid_id)
        draw.text((540, 160), sub_text, font=font_sub, fill=(255, 255, 255), anchor='mm')

        # B. Linhas dos Pilotos: Nome (2 primeiros nomes), ID e Pontos
        # Início dos textos das informações dos pilotos com espaçamento balanceado e respiro (X = 470)
        text_start_x = 470

        for idx in range(min(len(cls.SLOTS_Y), len(top_11))):
            item = top_11[idx]
            y1, y2 = cls.SLOTS_Y[idx]
            center_y = (y1 + y2) / 2

            team_key = item.get('team_key') or cls.match_team_key(item.get('team'))

            # Exibe apenas os 2 primeiros nomes do piloto (preservando preposições se houver)
            raw_real = item.get('nome_real') or item.get('nickname') or 'PILOTO'
            tokens = raw_real.strip().split()
            if len(tokens) >= 3 and tokens[1].lower() in ['de', 'da', 'do', 'dos', 'das']:
                name_text = " ".join(tokens[:3]).upper()
            elif len(tokens) >= 2:
                name_text = " ".join(tokens[:2]).upper()
            elif tokens:
                name_text = tokens[0].upper()
            else:
                name_text = 'PILOTO'

            # ID / Nickname do Piloto (menor, abaixo)
            raw_id = item.get('nickname') or ''
            id_text = raw_id.strip()

            # Coordenadas verticais de nome e ID
            y_name = center_y - 13
            y_id = center_y + 14

            # Contraste adaptativo: se a equipe for Haas (fundo cinza claro/branco), usa texto escuro
            is_light_card = (team_key == 'HAAS')
            name_color = (25, 25, 25) if is_light_card else (255, 255, 255)
            id_color = (85, 90, 100) if is_light_card else (215, 220, 230)

            draw.text((text_start_x, y_name), name_text, font=font_name, fill=name_color, anchor='lm')
            draw.text((text_start_x, y_id), id_text, font=font_id, fill=id_color, anchor='lm')

            # Pontuação na coluna vermelha à direita (centro X = 971)
            pts = item.get('pontos', 0)
            if isinstance(pts, (int, float)) and float(pts).is_integer():
                pts_str = str(int(pts))
            else:
                pts_str = f"{pts:g}"

            draw.text((971, center_y), pts_str, font=font_points, fill=(255, 255, 255), anchor='mm')

        # 5. Salva imagem final em buffer de memória PNG
        output_buffer = io.BytesIO()
        bg.save(output_buffer, format='PNG', optimize=True)
        output_buffer.seek(0)
        return output_buffer

