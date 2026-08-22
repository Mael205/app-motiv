"""Les défis de carte (§12.6, 21 août 2026).

Trente-six cartes épiques et légendaires tombaient au hasard. On ne pouvait
donc rien viser : une carte qui arrive par chance ne se prépare pas et ne se
raconte pas. Elles se gagnent maintenant par un compteur de discipline.

Ce que ce fichier verrouille, dans l'ordre d'importance :

1. **Une carte à défi ne s'obtient par aucun autre chemin.** Ni tirage, ni
   Forge. C'est toute la valeur du défi : le premier coup de chance ne doit pas
   effacer trois mois de régularité.
2. **Le défi ne donne que du cosmétique.** Le §17 tient des deux côtés — les
   reliques seules donnent un bonus, et elles pendent à un haut fait.
3. **L'attribution est idempotente**, parce qu'elle est appelée à chaque fin de
   session et à chaque étape close.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import progression
from forge.models import DayWindow, LootCard, LootDraw, Profile, Project, Session, Track
from forge.rules import defis as regles
from forge.rules import loot as loot_rules

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


class TestLeCatalogue:
    def test_chaque_defi_dit_sa_condition_en_francais(self):
        for defi in regles.CATALOGUE:
            assert defi.condition and "{" not in defi.condition

    def test_une_carte_n_a_jamais_deux_defis(self):
        cartes = [d.carte for d in regles.CATALOGUE]
        assert len(set(cartes)) == len(cartes)

    def test_la_legendaire_demande_toujours_plus_que_l_epique(self):
        """Une paire de la même voie est un palier et son horizon.

        Si la légendaire tombait avant l'épique, la progression se lirait à
        l'envers : la carte la plus rare serait la plus facile.
        """
        for voie in {d.voie for d in regles.CATALOGUE}:
            for fait in {d.fait for d in regles.CATALOGUE if d.voie == voie}:
                paliers = [
                    (loot_rules.PAR_CLE[d.carte].rarity, d.seuil)
                    for d in regles.CATALOGUE
                    if d.voie == voie and d.fait == fait
                ]
                epiques = [s for r, s in paliers if r == loot_rules.EPIQUE]
                legendaires = [s for r, s in paliers if r == loot_rules.LEGENDAIRE]
                if epiques and legendaires:
                    assert min(legendaires) > max(epiques), (voie, fait)

    def test_atteints_ne_rend_que_ce_qui_est_franchi(self):
        assert regles.atteints({"heures_totales": 49}) == []
        assert "theme_or_noir" in regles.atteints({"heures_totales": 50})
        assert "theme_eclipse" not in regles.atteints({"heures_totales": 50})


class TestLesDeuxAutresChemins:
    def test_le_tirage_ne_peut_pas_les_donner(self):
        tirables = {c.key for cartes in loot_rules.PAR_RARETE.values() for c in cartes}
        assert not (tirables & regles.CARTES_A_DEFI)

    def test_la_forge_les_refuse_avec_son_motif(self):
        carte = loot_rules.PAR_CLE["theme_eclipse"]
        ok, motif = loot_rules.peut_forger(carte, eclats=999_999, possedee=False)
        assert not ok and "se gagne" in motif

    def test_elles_restent_du_cosmetique(self):
        """Le §17 : la discipline achète du style, jamais un avantage."""
        for cle in regles.CARTES_A_DEFI:
            assert loot_rules.PAR_CLE[cle].kind in loot_rules.EMPLACEMENTS_ATTENDUS


@pytest.mark.django_db
class TestLAttribution:
    def test_une_carte_tombe_quand_le_compteur_franchit_le_seuil(self, user):
        assert progression.grant_defis(user) == []

        _heures(user, 50)
        obtenues = [c["key"] for c in progression.grant_defis(user)]
        assert "theme_or_noir" in obtenues
        assert LootCard.objects.filter(user=user, key="theme_or_noir").exists()

    def test_elle_ne_tombe_qu_une_fois(self, user):
        _heures(user, 50)
        progression.grant_defis(user)
        assert progression.grant_defis(user) == []

    def test_elle_ne_compte_pas_comme_un_tirage(self, user):
        """Sinon un défi rempli éloigne la prochaine carte rare : la discipline
        se paierait en malchance."""
        _heures(user, 50)
        progression.grant_defis(user)
        assert not LootDraw.objects.filter(user=user).exists()

    def test_l_ecran_recoit_de_quoi_dire_defi_et_non_trouvaille(self, user):
        _heures(user, 50)
        carte = next(c for c in progression.grant_defis(user) if c["key"] == "theme_or_noir")
        assert carte["reason_label"] == "Défi rempli"
        assert carte["defi"]["condition"] == "50 heures de travail cumulées"
        assert carte["shards"] == 0 and carte["duplicate"] is False


@pytest.mark.django_db
class TestCeQueLEcranMontre:
    def test_chaque_carte_dit_a_quoi_elle_sert(self, user):
        for cartes in progression.collection(user)["slots"].values():
            for entree in cartes:
                assert entree["utilite"]

    def test_une_carte_a_defi_montre_sa_condition_et_sa_progression(self, user):
        _heures(user, 20)
        entree = _carte(user, "theme_or_noir")
        assert entree["defi"]["condition"] == "50 heures de travail cumulées"
        assert entree["defi"]["valeur"] == 20 and entree["defi"]["seuil"] == 50

    def test_la_progression_ne_depasse_jamais_le_seuil(self, user):
        _heures(user, 300)
        assert _carte(user, "theme_or_noir")["defi"]["valeur"] == 50

    def test_une_carte_de_tirage_n_a_pas_de_defi(self, user):
        assert _carte(user, "theme_braise")["defi"] is None


def _carte(user, cle: str) -> dict:
    for cartes in progression.collection(user)["slots"].values():
        for entree in cartes:
            if entree["key"] == cle:
                return entree
    raise AssertionError(f"carte absente : {cle}")


def _heures(user, combien: int) -> None:
    """Pose assez de sessions pour que le compteur d'heures atteigne `combien`."""
    projet = Project.objects.get(user=user, name="Bestiaire")
    for i in range(combien):
        jour = LUNDI + timedelta(days=i)
        Session.objects.create(
            user=user,
            project=projet,
            coach_day=jour,
            started_at=datetime(jour.year, jour.month, jour.day, 21, tzinfo=PARIS),
            actual_minutes=60,
            status=Session.DONE,
        )


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)

    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
    return user
