"""Les cartes donnent des buffs, les hauts faits donnent l'apparence (16/09/2026).

L'ancienne règle du §17 — *le loot est de l'apparence, jamais du pouvoir* —
existait contre un mode de défaillance précis : récompenser la chance plutôt que
le travail. Elle est levée, donc ce qui la remplaçait doit être tenu **ici**,
sans quoi personne ne s'apercevra de sa disparition :

- une carte ne tombe jamais sans travail (le tirage est déjà payé) ;
- une carte est une **charge**, jamais un passif : la malchance coûte une
  occasion, pas une puissance qui manque tous les jours ;
- **aucune carte ne touche au cadre**, sauf le sas. C'est la frontière qui se
  perdra au premier effet ajouté à la va-vite.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from forge import progression, services
from forge.models import Garde, GardeDay, LootCard, Profile, Project, Session, Track
from forge.rules import buffs as buff_rules

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 9, 14)


@pytest.fixture
def user(db, django_user_model):
    user = django_user_model.objects.create_user(username="test", password="test")
    Profile.objects.create(user=user)
    Track.objects.create(user=user, kind=Track.ATELIER)
    return user


def carte(user, key: str, charges: int = 1) -> LootCard:
    buff = buff_rules.PAR_CLE[key]
    return LootCard.objects.create(
        user=user, key=key, rarity=buff.rarity, kind="buff", copies=charges
    )


class TestLaFrontiere:
    """Ce qu'aucune carte n'a le droit de faire."""

    def test_seul_le_sas_touche_au_cadre(self):
        hors_jeu = [
            b for b in buff_rules.CATALOGUE
            if buff_rules.touche_au_cadre(b.effect)
        ]

        assert {b.effect for b in hors_jeu} <= set(buff_rules.EFFETS_DE_SAS)

    def test_aucun_effet_ne_touche_au_streak_ni_au_rang(self):
        """Une carte qui rendrait un bouclier ferait du cœur du système un objet."""
        interdits = ("streak", "bouclier", "shield", "rang", "rank", "slot", "garde", "blocage")

        for buff in buff_rules.CATALOGUE:
            assert not any(mot in buff.effect for mot in interdits)

    def test_le_catalogue_n_invente_aucun_effet(self):
        for buff in buff_rules.CATALOGUE:
            assert buff.effect in buff_rules.EFFETS

    def test_chaque_carte_dit_ce_qu_elle_fait(self):
        for buff in buff_rules.CATALOGUE:
            assert buff.ligne and buff.lore


class TestLaRotation:
    def test_chaque_saison_a_son_lot(self):
        un, deux = buff_rules.lot_de_saison(1), buff_rules.lot_de_saison(2)

        assert un != deux
        assert len(un) == buff_rules.TAILLE_DU_LOT

    def test_le_lot_est_toujours_le_meme_pour_une_saison(self):
        """Un lot tiré au sort à chaque lecture ferait clignoter le catalogue."""
        assert buff_rules.lot_de_saison(3) == buff_rules.lot_de_saison(3)

    def test_deux_saisons_voisines_partagent_une_partie_du_lot(self):
        """Une carte manquée revient — plus tard, pas jamais."""
        commun = set(buff_rules.lot_de_saison(1)) & set(buff_rules.lot_de_saison(2))

        assert commun

    def test_tout_le_catalogue_finit_par_sortir(self):
        vus = set()
        for index in range(1, len(buff_rules.CATALOGUE) + 1):
            vus |= set(buff_rules.lot_de_saison(index))

        assert vus == set(buff_rules.CATALOGUE)


@pytest.mark.django_db
class TestDepenserUneCharge:
    def test_armer_consomme_une_charge(self, user):
        carte(user, "etincelle", charges=2)

        progression.armer_buff(user, "etincelle", today=LUNDI)

        assert LootCard.objects.get(user=user, key="etincelle").copies == 1

    def test_sans_charge_rien_ne_s_arme(self, user):
        with pytest.raises(ValueError, match="Aucune charge"):
            progression.armer_buff(user, "etincelle", today=LUNDI)

    def test_deux_effets_du_meme_genre_ne_s_empilent_pas(self, user):
        """Deux « ×2 » sur la même séance donneraient un ×4 que personne n'a calibré."""
        carte(user, "etincelle")
        carte(user, "braise_ardente")

        progression.armer_buff(user, "etincelle", today=LUNDI)

        with pytest.raises(ValueError, match="doublon"):
            progression.armer_buff(user, "braise_ardente", today=LUNDI)

    def test_un_buff_arme_hier_ne_joue_pas_aujourd_hui(self, user):
        carte(user, "etincelle")
        progression.armer_buff(user, "etincelle", today=LUNDI - timedelta(days=1))

        assert progression.buff_arme(user, buff_rules.XP_SEANCE, day=LUNDI) is None


@pytest.mark.django_db
class TestCeQueLesBuffsFont:
    def cloturer(self, user, minutes=30) -> dict:
        """Une séance de trente minutes, clôturée comme l'app le fait."""
        from django.utils import timezone as dj

        projet, _ = Project.objects.get_or_create(
            user=user, track=Track.objects.get(user=user), name="Evolve", defaults={"slot": 1}
        )
        debut = dj.now() - timedelta(minutes=minutes)
        session = Session.objects.create(
            user=user,
            project=projet,
            planned_minutes=minutes,
            status=Session.RUNNING,
            coach_day=_aujourdhui(user),
            started_at=debut,
        )
        return session, services.end_session(session, next_action="la suite")

    def test_l_xp_de_la_seance_est_majoree_et_la_charge_consommee(self, user):
        """Deux séances du même jour ne se comparent pas — la seconde rapporte
        moins par construction (forfait de première séance, dégressivité). C'est
        donc le facteur inscrit au détail qui fait foi, et le barème qui est
        testé ailleurs."""
        jour = _aujourdhui(user)
        carte(user, "braise_ardente")       # ×1,5
        progression.armer_buff(user, "braise_ardente", today=jour)

        _, resultat = self.cloturer(user)

        assert resultat["breakdown"]["buff_xp"] == 1.5
        assert resultat["breakdown"]["base_total"] > resultat["breakdown"]["base"]
        assert progression.buff_arme(user, buff_rules.XP_SEANCE, day=jour) is None

    def test_sans_carte_le_facteur_reste_a_un(self, user):
        _, resultat = self.cloturer(user)

        assert resultat["breakdown"]["buff_xp"] == 1.0

    def test_les_minutes_ne_bougent_jamais(self, user):
        """Le fantôme compare des minutes (§12.7) : une carte ne doit pas les toucher."""
        carte(user, "coup_franc")
        progression.armer_buff(user, "coup_franc", today=_aujourdhui(user))

        session, _ = self.cloturer(user)

        session.refresh_from_db()
        assert session.actual_minutes == 30


@pytest.mark.django_db
class TestLesCartesDeSas:
    def client(self, user):
        api = APIClient()
        api.force_authenticate(user=user)
        return api

    def test_la_rallonge_allonge_le_sas(self, user):
        carte(user, "longue_respiration")   # +20 min
        progression.armer_buff(user, "longue_respiration", today=_aujourdhui(user))

        reponse = self.client(user).post("/api/relax/start")

        assert reponse.json()["minutes"] == 40

    def test_le_blanc_seing_epargne_la_journee_de_reseaux(self, user):
        garde = Garde.objects.create(
            user=user, name="Réseaux", weekly_budget=2, auto_category="reseaux"
        )
        carte(user, "blanc_seing")
        progression.armer_buff(user, "blanc_seing", today=_aujourdhui(user))

        self.client(user).post("/api/relax/start")

        assert not GardeDay.objects.filter(garde=garde).exists()

    def test_sans_carte_le_sas_coute_sa_journee(self, user):
        garde = Garde.objects.create(
            user=user, name="Réseaux", weekly_budget=2, auto_category="reseaux"
        )

        self.client(user).post("/api/relax/start")

        assert GardeDay.objects.get(garde=garde).occurred is True

    def test_le_second_souffle_rouvre_un_sas_deja_pris(self, user):
        client = self.client(user)
        client.post("/api/relax/start")
        refus = client.post("/api/relax/start")
        assert refus.status_code == 409

        carte(user, "second_souffle")
        progression.armer_buff(user, "second_souffle", today=_aujourdhui(user))
        deuxieme = client.post("/api/relax/start")

        assert deuxieme.status_code == 201


@pytest.mark.django_db
class TestLesSkinsViennentDesHautsFaits:
    def test_un_haut_fait_donne_une_apparence(self, user):
        obtenus = progression.grant_skins_for(user, ["premier_sang"])

        assert obtenus and obtenus[0]["kind"] != "buff"
        assert LootCard.objects.filter(user=user, reason="haut_fait").count() == 1

    def test_le_meme_haut_fait_ne_donne_pas_deux_fois(self, user):
        progression.grant_skins_for(user, ["premier_sang"])
        progression.grant_skins_for(user, ["premier_sang"])

        assert LootCard.objects.filter(user=user, reason="haut_fait").count() == 1

    def test_deux_hauts_faits_donnent_deux_apparences_differentes(self, user):
        obtenus = progression.grant_skins_for(user, ["premier_sang", "premiere_etape"])

        assert len({c["key"] for c in obtenus}) == 2

    def test_une_apparence_n_est_jamais_une_carte_de_buff(self, user):
        """Sinon une apparence donnerait du pouvoir, et on aurait tout inversé pour rien."""
        progression.grant_skins_for(user, ["premier_sang", "premiere_etape"])

        for ligne in LootCard.objects.filter(user=user, reason="haut_fait"):
            assert ligne.key not in buff_rules.PAR_CLE


def _aujourdhui(user):
    from django.utils import timezone as dj

    from forge.rules.calendar import coach_day

    profile = user.profile
    return coach_day(dj.now(), profile.timezone_name, profile.day_rollover_hour)
