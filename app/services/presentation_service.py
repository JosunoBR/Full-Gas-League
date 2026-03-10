from app.utils import ORDEM_CARROS

class PresentationService:
    @staticmethod
    def assign_ballast(standings_list, grid_config):
        """
        Atribui o carro de lastro para cada piloto na lista de classificação.
        Modifica a lista de dicionários in-place.
        """
        if not grid_config.exibir_lastro:
            for item in standings_list:
                item["carro"] = "-"
            return

        for i, item in enumerate(standings_list):
            if i < len(ORDEM_CARROS):
                item["carro"] = ORDEM_CARROS[i]
            else:
                item["carro"] = "McLaren (Extra)"

    @staticmethod
    def get_pilot_photo_for_grid(pilot_obj, grid_id):
        """
        Obtém a URL da foto correta para o piloto, considerando a foto específica do grid.
        """
        grid_photo = next((gp for gp in pilot_obj.grid_photos if getattr(gp, "grid_id", None) == grid_id), None)
        return grid_photo.foto_url if grid_photo else pilot_obj.foto_url