import re

class SimHubService:
    """
    Serviço para análise, validação de pista e parsing de arquivos CSV de telemetria do SimHub.
    """

    # Mapeamento de termos de pistas entre SimHub (Inglês) e Sistema (Português/GP)
    TRACK_MAP = {
        "bahrain": ["bahrain", "bahrein", "sakhir"],
        "jeddah": ["jeddah", "saudi", "arábia", "arabia"],
        "albert park": ["albert", "australia", "austrália", "melbourne"],
        "suzuka": ["suzuka", "japan", "japão", "japao"],
        "shanghai": ["shanghai", "china"],
        "miami": ["miami"],
        "imola": ["imola", "ímola", "emilia"],
        "monaco": ["monaco", "mônaco", "monte carlo"],
        "villeneuve": ["villeneuve", "canada", "canadá", "montreal"],
        "barcelona": ["barcelona", "catalunya", "espanha", "spain"],
        "red bull ring": ["austria", "ústria", "spielberg", "red bull ring"],
        "silverstone": ["silverstone", "britain", "grã-bretanha", "gra-bretanha", "uk"],
        "hungaroring": ["hungaroring", "hungaria", "hungria", "budapest"],
        "spa": ["spa", "francorchamps", "belgium", "bélgica", "belgica"],
        "zandvoort": ["zandvoort", "dutch", "holanda", "netherlands"],
        "monza": ["monza", "italy", "itália", "italia"],
        "baku": ["baku", "azerbaijan", "azerbaijão", "azerbaijao"],
        "singapore": ["singapore", "singapura"],
        "americas": ["austin", "cota", "americas", "usa", "eua"],
        "rodriguez": ["mexico", "méxico", "autodromo hermanas rodriguez"],
        "interlagos": ["interlagos", "brazil", "brasil", "são paulo", "sao paulo"],
        "las vegas": ["vegas", "las vegas"],
        "losail": ["losail", "lusail", "qatar", "catar"],
        "yas marina": ["yas", "marina", "abu dhabi", "emirat"]
    }

    @classmethod
    def validate_track(cls, filename, race_pista, race_nome_gp):
        """
        Verifica se o nome do arquivo CSV do SimHub corresponde à pista da corrida.
        Retorna (is_valid, detected_track_name, warning_msg).
        """
        filename_lower = (filename or '').lower()
        race_pista_lower = (race_pista or '').lower()
        race_gp_lower = (race_nome_gp or '').lower()

        # Identifica a pista no arquivo CSV
        detected_key = None
        for key, aliases in cls.TRACK_MAP.items():
            if any(alias in filename_lower for alias in aliases):
                detected_key = key
                break

        if not detected_key:
            # Se não encontrou no mapeamento, extrai o primeiro trecho antes da data/sublinhado
            raw_name = filename.split('_')[0].split('-')[0].strip()
            detected_name = raw_name if raw_name else "Pista Desconhecida"
            return True, detected_name, None # Permite com aviso neutro

        aliases = cls.TRACK_MAP[detected_key]
        matches_pista = any(alias in race_pista_lower for alias in aliases)
        matches_gp = any(alias in race_gp_lower for alias in aliases)

        detected_name = detected_key.title()

        if matches_pista or matches_gp:
            return True, detected_name, None
        else:
            warning = (
                f"ATENÇÃO DE SEGURANÇA: O arquivo CSV enviado pertence a '{detected_name}', "
                f"mas a corrida atual é '{race_nome_gp}' ({race_pista})."
            )
            return False, detected_name, warning

    @classmethod
    def parse_time_to_seconds(cls, time_str):
        """
        Converte tempo no formato MM:SS.MS (ex: '01:31.412') para segundos booleano/float.
        """
        if not time_str or time_str.upper() in ['NO TIME', 'DNF', 'DSQ', 'DNS', '-']:
            return float('inf')
        try:
            s = time_str.strip()
            if ':' in s:
                parts = s.split(':')
                return float(parts[0]) * 60 + float(parts[1])
            return float(s)
        except Exception:
            return float('inf')

    @classmethod
    def parse_simhub_csv(cls, csv_content_str, eligible_pilots, all_pilots=None):
        """
        Lê o conteúdo do arquivo CSV do SimHub com as seções === QUALIFYING === e === RACE ===
        e cruza com a lista de pilotos elegíveis cadastrados na liga.
        """
        lines = [line.strip() for line in csv_content_str.splitlines() if line.strip()]
        
        section = None
        qualy_data = {}
        sprint_rows = []
        race_rows = []
        
        for line in lines:
            line_up = line.upper()
            if '=== SPRINT QUALIFYING ===' in line_up or '=== SPRINT SHOOTOUT ===' in line_up:
                section = 'SPRINT_QUALIFYING'
                continue
            elif '=== SPRINT ===' in line_up or '=== SPRINT RACE ===' in line_up:
                section = 'SPRINT'
                continue
            elif '=== QUALIFYING ===' in line_up:
                section = 'QUALIFYING'
                continue
            elif '=== RACE ===' in line_up or '=== MAIN RACE ===' in line_up:
                section = 'RACE'
                continue
                
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 4:
                continue
                
            pos_str = parts[0]
            if not pos_str.isdigit():
                continue
                
            pos = int(pos_str)
            gamertag = parts[1]
            nickname = parts[2]
            team_name = parts[3]
            time_val = parts[4] if len(parts) > 4 else ''
            
            if section in ['QUALIFYING', 'SPRINT_QUALIFYING']:
                qualy_data[gamertag.lower()] = {
                    'grid_pos': pos,
                    'gamertag': gamertag,
                    'nickname': nickname,
                    'qualy_time': time_val
                }
                qualy_data[nickname.lower()] = qualy_data[gamertag.lower()]
            elif section == 'SPRINT':
                pits = int(parts[5]) if (len(parts) > 5 and parts[5].isdigit()) else 0
                sprint_rows.append({
                    'finish_pos': pos,
                    'gamertag': gamertag,
                    'nickname': nickname,
                    'team': team_name,
                    'best_lap': time_val,
                    'pits': pits
                })
            elif section == 'RACE':
                pits = int(parts[5]) if (len(parts) > 5 and parts[5].isdigit()) else 0
                race_rows.append({
                    'finish_pos': pos,
                    'gamertag': gamertag,
                    'nickname': nickname,
                    'team': team_name,
                    'best_lap': time_val,
                    'pits': pits
                })

        # Mapeador de Pilotos (Nickname, Gamertag & Username da Liga)
        pilots_map = {}
        search_pilots = list(eligible_pilots)
        if all_pilots:
            for ap in all_pilots:
                if ap not in search_pilots:
                    search_pilots.append(ap)

        for p in search_pilots:
            if p.nickname:
                pilots_map[p.nickname.lower().strip()] = p
            if hasattr(p, 'user') and p.user and p.user.username:
                pilots_map[p.user.username.lower().strip()] = p

        matched_positions = {}
        unmatched_drivers = []
        pole_info = None

        # Identifica Pole Sitter a partir do Qualy (P1)
        for key, qdata in qualy_data.items():
            if qdata.get('grid_pos') == 1:
                pole_driver_name = qdata.get('nickname') or qdata.get('gamertag')
                pole_pilot = cls._match_pilot(pole_driver_name, pilots_map)
                pole_info = {
                    'pilot_id': pole_pilot.id if pole_pilot else None,
                    'driver_name': pole_driver_name,
                    'qualy_time': qdata.get('qualy_time')
                }
                break

        # Identifica a Volta Rápida Global da Corrida (Menor tempo de volta)
        min_race_sec = float('inf')
        fastest_driver_index = None

        for idx, rrow in enumerate(race_rows):
            sec = cls.parse_time_to_seconds(rrow['best_lap'])
            if sec < min_race_sec:
                min_race_sec = sec
                fastest_driver_index = idx

        # Processa cada piloto da corrida garantindo que nenhum piloto seja selecionado duas vezes
        used_pilot_ids = set()

        for idx, rrow in enumerate(race_rows):
            finish_pos = rrow['finish_pos']
            driver_name = rrow['nickname'] if rrow['nickname'] != 'Unknown' else rrow['gamertag']
            pilot = cls._match_pilot(driver_name, pilots_map, used_pilot_ids=used_pilot_ids)
            if not pilot and rrow['gamertag'] and rrow['gamertag'] != driver_name:
                pilot = cls._match_pilot(rrow['gamertag'], pilots_map, used_pilot_ids=used_pilot_ids)

            # Busca dados do Qualy para este piloto
            qentry = qualy_data.get(driver_name.lower()) or qualy_data.get(rrow['gamertag'].lower())
            grid_pos = qentry['grid_pos'] if qentry else None
            qualy_time = qentry['qualy_time'] if qentry else None

            is_vr = (idx == fastest_driver_index) and (min_race_sec < float('inf'))

            if pilot:
                used_pilot_ids.add(pilot.id)
                matched_positions[finish_pos] = {
                    'pilot_id': pilot.id,
                    'pilot_nickname': pilot.nickname,
                    'grid_largada': grid_pos,
                    'melhor_volta': rrow['best_lap'],
                    'tempo_qualy': qualy_time,
                    'pit_stops': rrow['pits'],
                    'volta_rapida': is_vr
                }
            else:
                unmatched_drivers.append({
                    'pos': finish_pos,
                    'driver_name': driver_name,
                    'gamertag': rrow['gamertag'],
                    'team': rrow['team']
                })

        # Processa cada piloto da corrida Sprint (se houver)
        sprint_positions = {}
        min_sprint_sec = float('inf')
        fastest_sprint_driver_index = None

        for idx, srow in enumerate(sprint_rows):
            sec = cls.parse_time_to_seconds(srow['best_lap'])
            if sec < min_sprint_sec:
                min_sprint_sec = sec
                fastest_sprint_driver_index = idx

        for idx, srow in enumerate(sprint_rows):
            finish_pos = srow['finish_pos']
            driver_name = srow['nickname'] if srow['nickname'] != 'Unknown' else srow['gamertag']
            pilot = cls._match_pilot(driver_name, pilots_map, used_pilot_ids=used_pilot_ids)
            if not pilot and srow['gamertag'] and srow['gamertag'] != driver_name:
                pilot = cls._match_pilot(srow['gamertag'], pilots_map, used_pilot_ids=used_pilot_ids)
            is_sprint_vr = (idx == fastest_sprint_driver_index) and (min_sprint_sec < float('inf'))

            if pilot:
                sprint_positions[finish_pos] = {
                    'pilot_id': pilot.id,
                    'pilot_nickname': pilot.nickname,
                    'melhor_volta_sprint': srow['best_lap'],
                    'pit_stops': srow['pits'],
                    'sprint_vr': is_sprint_vr
                }

        # Busca por metadados no arquivo CSV (SC/VSC, Clima, Total de Voltas)
        sc_vsc_info = None
        clima_temp = None
        total_voltas = None

        for line in lines:
            l_up = line.upper()
            if 'SC:' in l_up or 'SAFETY CAR:' in l_up or 'VSC:' in l_up:
                sc_vsc_info = line.split(':', 1)[1].strip() if ':' in line else line
            elif 'CLIMA:' in l_up or 'TEMPERATURA:' in l_up or 'PISTA:' in l_up:
                clima_temp = line.split(':', 1)[1].strip() if ':' in line else line
            elif 'VOLTAS:' in l_up or 'TOTAL VOLTAS:' in l_up or 'LAPS:' in l_up or 'TOTAL LAPS:' in l_up:
                v_str = line.split(':', 1)[1].strip() if ':' in line else ''
                # Extrai os dígitos do valor da linha de voltas
                match_digits = re.search(r'\d+', v_str)
                if match_digits:
                    total_voltas = int(match_digits.group())

        # Se não encontrou o metadado explícito nas linhas de cabeçalho, busca por padrões de voltas ou maior contagem de voltas nas linhas do arquivo
        if not total_voltas:
            lap_matches = []
            for line in lines:
                # Procura padrões como "36 voltas", "36 laps", "voltas: 36", "laps = 36", etc.
                matches = re.findall(r'(?:total\s*voltas|total\s*laps|voltas|laps)\s*[:=]?\s*(\d+)', line, re.IGNORECASE)
                for m in matches:
                    if m.isdigit():
                        lap_matches.append(int(m))
            if lap_matches:
                total_voltas = max(lap_matches)

        if not sc_vsc_info:
            sc_vsc_info = 'Sem SC / VSC'

        return {
            'pole': pole_info,
            'metadata': {
                'sc_vsc_info': sc_vsc_info,
                'clima_temp': clima_temp,
                'total_voltas': total_voltas
            },
            'matched_positions': matched_positions,
            'sprint_positions': sprint_positions,
            'unmatched_drivers': unmatched_drivers,
            'total_qualifying': len(qualy_data),
            'total_sprint': len(sprint_rows),
            'total_race': len(race_rows)
        }

    COMMON_TAGS = {
        'dut', 'sfa', 'bzk', 'url', 'mdr', 'rs', 'bgr', 'f1', 'gp', 'team', 'vr',
        'racing', 'red', 'bull', 'ferrari', 'mclaren', 'audi', 'haas', 'williams',
        'alpine', 'aston', 'martin', 'mercedes', 'cadillac', 'unknown'
    }

    @classmethod
    def _match_pilot(cls, driver_name, pilots_map, used_pilot_ids=None):
        """
        Auxiliar inteligente para casar o nome do piloto no CSV com os cadastrados no banco.
        Evita duplicações verificando used_pilot_ids e ignorando tags de clãs/equipes compartilhadas.
        """
        if not driver_name:
            return None
        if used_pilot_ids is None:
            used_pilot_ids = set()

        name_clean = driver_name.lower().strip()

        def is_available(p):
            return p and p.id not in used_pilot_ids
        
        # 1. Correspondência exata
        if name_clean in pilots_map and is_available(pilots_map[name_clean]):
            return pilots_map[name_clean]

        import re

        # 2. Normalização simples (remover hífens, underlines, pontos e espaços)
        norm_name = re.sub(r'[^a-z0-9]', '', name_clean)
        for k, p in pilots_map.items():
            if not is_available(p):
                continue
            k_norm = re.sub(r'[^a-z0-9]', '', k)
            if norm_name == k_norm:
                return p

        # 3. Busca por tokens/palavras do apelido, IGNORANDO tags de clã/equipe (ex: DUT, MDR, SFA)
        tokens = [t for t in re.split(r'[\s_\-\.]+', name_clean) if len(t) >= 3 and t.lower() not in cls.COMMON_TAGS]
        for t in tokens:
            t_norm = re.sub(r'[^a-z0-9]', '', t)
            for k, p in pilots_map.items():
                if not is_available(p):
                    continue
                k_clean_tokens = [re.sub(r'[^a-z0-9]', '', kt) for kt in re.split(r'[\s_\-\.]+', k) if kt.lower() not in cls.COMMON_TAGS]
                for kt_norm in k_clean_tokens:
                    if len(t_norm) >= 3 and len(kt_norm) >= 3 and (t_norm == kt_norm or t_norm in kt_norm or kt_norm in t_norm):
                        return p

        # 4. Busca por substrings longas (excluindo tags comuns)
        clean_name_no_tags = "".join([t for t in re.split(r'[\s_\-\.]+', name_clean) if t.lower() not in cls.COMMON_TAGS])
        norm_no_tags = re.sub(r'[^a-z0-9]', '', clean_name_no_tags)

        if len(norm_no_tags) >= 4:
            for k, p in pilots_map.items():
                if not is_available(p):
                    continue
                k_clean_no_tags = "".join([kt for kt in re.split(r'[\s_\-\.]+', k) if kt.lower() not in cls.COMMON_TAGS])
                k_norm = re.sub(r'[^a-z0-9]', '', k_clean_no_tags)
                if len(k_norm) >= 4 and (norm_no_tags in k_norm or k_norm in norm_no_tags):
                    return p

        return None
