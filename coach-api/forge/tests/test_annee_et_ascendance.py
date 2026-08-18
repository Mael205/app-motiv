"""L'année de douze saisons, l'ascendance, et le contenu qui va avec.

Le prestige est la mécanique la plus facile à rendre malhonnête : il touche à
des compteurs que l'utilisateur a mis un an à monter. Trois propriétés le
tiennent, et ce fichier ne teste presque rien d'autre.

1. **Rien n'est effacé.** Les deux resets — l'XP et le rang — déplacent un
   horizon de lecture. Aucune session, aucune semaine ne disparaît, et la trace
   longue continue de tout porter.
2. **Les slots sont gravés.** Le rang repart de F, mais reprendre un slot
   gèlerait un projet en cours, ce que le §4.3 interdit.
3. **Aucune voie ne donne de la puissance.** Capacité, choix, ou mécanique
   nouvelle — jamais un avantage sur la mesure du travail.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import progression, season_flow, services, trace
from forge.models import (
    Ascendance,
    Commitment,
    DayWindow,
    LootCard,
    Profile,
    Project,
    Season,
    Session,
    Track,
)
from forge.rules import loot as loot_rules
from forge.rules import seasons as season_rules
from forge.rules import years as regles

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


# --------------------------------------------------------------------------
# L'année, en logique pure
# --------------------------------------------------------------------------

class TestLAnnee:
    def test_douze_saisons_font_une_annee(self):
        assert regles.annee_de(1) == 1 and regles.annee_de(12) == 1
        assert regles.annee_de(13) == 2 and regles.annee_de(24) == 2

    def test_le_rang_dans_l_annee_repart_a_un(self):
        assert regles.rang_dans_l_annee(12) == 12
        assert regles.rang_dans_l_annee(13) == 1

    def test_seule_la_douzieme_ferme_l_annee(self):
        assert regles.ferme_l_annee(12) and regles.ferme_l_annee(24)
        assert not regles.ferme_l_annee(11) and not regles.ferme_l_annee(13)

    def test_le_compte_a_rebours(self):
        assert regles.saisons_restantes(1) == 12
        assert regles.saisons_restantes(12) == 1

    def test_chaque_identite_sort_une_fois_par_an(self):
        for annee in range(1, 8):
            ordre = regles.ordre_des_identites(annee, 12)
            assert sorted(ordre) == list(range(12))

    def test_les_annees_ne_rejouent_pas_le_meme_ordre(self):
        ordres = {tuple(regles.ordre_des_identites(a, 12)) for a in range(1, 8)}
        assert len(ordres) == 7


class TestLesVoies:
    def test_aucune_voie_ne_touche_a_la_mesure(self):
        """Une voie ouvre une mécanique, une capacité ou un choix. Jamais un
        avantage sur ce qui mesure le travail."""
        tous = regles.effets([v.cle for v in regles.CATALOGUE for _ in range(v.prises_max)])
        for interdit in ("xp_multiplier", "minutes_bonus", "degats_bonus", "streak_bonus"):
            assert not hasattr(tous, interdit)

    def test_ampleur_se_prend_deux_fois_au_maximum(self):
        assert regles.effets([regles.AMPLEUR]).slots_bonus == 1
        assert regles.effets([regles.AMPLEUR] * 5).slots_bonus == 2

    def test_ampleur_disparait_au_plafond_du_paragraphe_4_3(self):
        """Le plafond de la spec ne se contourne pas par une mécanique ajoutée
        par-dessus."""
        ouvertes = {v.cle for v in regles.voies_disponibles([], slots_actuels=regles.SLOTS_MAX)}
        assert regles.AMPLEUR not in ouvertes

    def test_exigence_monte_le_plancher_et_paie_en_eclats(self):
        effets = regles.effets([regles.EXIGENCE])
        assert effets.plancher_bonus == regles.EXIGENCE_MINUTES
        assert effets.eclats_bonus > 0

    def test_une_voie_prise_ne_se_repropose_pas(self):
        ouvertes = {v.cle for v in regles.voies_disponibles([regles.MEMOIRE])}
        assert regles.MEMOIRE not in ouvertes and regles.FORGE in ouvertes

    def test_le_titre_de_l_annee_ne_juge_pas(self):
        for abattus in (0, 3, 9, 12):
            texte = regles.titre_de_l_annee(2, abattus).lower()
            for mot in ("raté", "mauvais", "seulement", "faible", "bravo"):
                assert mot not in texte


# --------------------------------------------------------------------------
# L'ascendance, en base
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestLAscendance:
    def test_la_douzieme_cloture_ferme_l_annee(self, user):
        bilan = _clore_douze_saisons(user)
        assert bilan["annee"]["year"] == 1
        assert Ascendance.objects.filter(user=user).count() == 1

    def test_l_xp_repart_mais_rien_n_est_efface(self, user):
        """Le mécanisme tient en une date : l'horizon avance, les sessions restent."""
        travailler(user, LUNDI, xp=400)
        assert services.current_xp(user) == 400

        _clore_douze_saisons(user, today=LUNDI + timedelta(days=1))

        assert services.current_xp(user) == 0
        assert Session.objects.filter(user=user, status=Session.DONE).count() == 1
        assert _compteur(trace.longue(user), "XP cumulée") == 400

    def test_le_rang_repart_mais_les_semaines_restent(self, user):
        projet = Project.objects.get(user=user)
        for i in range(3):
            Commitment.objects.create(
                project=projet, week_start=LUNDI - timedelta(days=7 * (i + 1)),
                planned_sessions=3, done_sessions=3,
            )
        avant = services.rank_state(user, today=LUNDI)["weeks_kept"]
        assert avant == 3

        _clore_douze_saisons(user, today=LUNDI)

        assert services.rank_state(user, today=LUNDI + timedelta(days=14))["weeks_kept"] == 0
        assert Commitment.objects.filter(project__user=user).count() == 3

    def test_les_slots_sont_graves(self, user):
        """Le rang les reprendrait, et un projet en cours se retrouverait gelé."""
        _clore_douze_saisons(user)
        ascendance = Ascendance.objects.get(user=user)
        assert ascendance.slots_engraved >= 3
        assert services.rank_state(user, today=LUNDI + timedelta(days=1))["slots"] >= 3

    def test_la_voie_se_choisit_apres_avoir_lu_le_bilan(self, user):
        bilan = _clore_douze_saisons(user)
        assert bilan["annee"]["voie"] == ""
        assert season_flow.annee_en_attente(user) is not None

        season_flow.choisir_la_voie(user, regles.FORGE)
        assert Ascendance.objects.get(user=user).voie == regles.FORGE
        assert season_flow.annee_en_attente(user) is None

    def test_une_voie_hors_catalogue_est_refusee(self, user):
        _clore_douze_saisons(user)
        with pytest.raises(ValueError, match="ouverte"):
            season_flow.choisir_la_voie(user, "toute_puissance")

    def test_une_voie_ne_se_reprend_pas(self, user):
        _clore_douze_saisons(user)
        season_flow.choisir_la_voie(user, regles.ECHO)
        with pytest.raises(ValueError, match="Aucune année"):
            season_flow.choisir_la_voie(user, regles.MEMOIRE)

    def test_une_voie_non_choisie_n_ouvre_rien(self, user):
        """Ce qui rend le choix réel plutôt qu'une formalité à cliquer plus tard."""
        _clore_douze_saisons(user)
        assert not services.ascendance_effects(user).any


# --------------------------------------------------------------------------
# La Forge
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestLaForge:
    def test_elle_est_fermee_sans_ascendance(self, user):
        user.profile.shards = 10_000
        user.profile.save()
        with pytest.raises(ValueError, match="pas ouverte"):
            progression.forger(user, "theme_braise")

    def test_elle_fait_enfin_descendre_les_eclats(self, user):
        """Le seul endroit du produit où des Éclats sortent."""
        _ouvrir_la_forge(user, eclats=1000)
        carte = loot_rules.PAR_CLE["theme_encre"]

        resultat = progression.forger(user, carte.key)

        user.profile.refresh_from_db()
        assert user.profile.shards == 1000 - loot_rules.prix_de_forge(carte)
        assert resultat["shards"] < 0
        assert LootCard.objects.filter(user=user, key=carte.key).exists()

    def test_sans_assez_d_eclats_elle_refuse(self, user):
        _ouvrir_la_forge(user, eclats=5)
        with pytest.raises(ValueError, match="Éclats demandés"):
            progression.forger(user, "theme_eclipse")

    def test_une_carte_deja_possedee_est_refusee(self, user):
        _ouvrir_la_forge(user, eclats=1000)
        LootCard.objects.create(user=user, key="theme_braise", rarity="commun", kind="theme")
        with pytest.raises(ValueError, match="déjà"):
            progression.forger(user, "theme_braise")

    def test_forger_coute_bien_plus_que_ce_qu_un_doublon_rapporte(self):
        """Si forger devenait rentable, l'ouverture d'une carte perdrait son sens."""
        for rarete, prix in loot_rules.PRIX_FORGE.items():
            assert prix >= loot_rules.ECLATS_PAR_RARETE[rarete] * 5

    def test_la_carte_forgee_n_entre_pas_dans_la_pitie(self, user):
        """Un achat n'est pas un tirage : l'y compter reviendrait à acheter sa chance."""
        _ouvrir_la_forge(user, eclats=1000)
        avant = progression._pity(user)
        progression.forger(user, "theme_encre")
        assert progression._pity(user) == avant


# --------------------------------------------------------------------------
# Le contenu
# --------------------------------------------------------------------------

class TestLeContenu:
    def test_douze_identites_douze_boss_douze_modificateurs(self):
        assert len(season_rules.SEASON_POOL) == regles.SAISONS_PAR_AN
        assert len(season_rules.BOSSES) == regles.SAISONS_PAR_AN
        assert len(season_rules.MODIFIERS) >= regles.SAISONS_PAR_AN

    def test_chaque_boss_a_ses_trois_phases(self):
        from forge.rules import bossphases

        for boss in season_rules.BOSSES:
            assert len(bossphases.PHASES[boss["key"]]) == 3

    def test_les_cles_de_carte_et_leurs_charges_sont_uniques(self):
        cles = [c.key for c in loot_rules.CATALOGUE]
        charges = [c.payload for c in loot_rules.CATALOGUE]
        assert len(set(cles)) == len(cles)
        assert len(set(charges)) == len(charges)

    def test_chaque_rareté_a_de_quoi_tirer_dans_chaque_emplacement(self):
        for rarete in loot_rules.RARETES:
            assert loot_rules.PAR_RARETE[rarete], rarete

    def test_chaque_relique_pend_a_un_haut_fait_qui_existe(self):
        """Quatre reliques sur cinq étaient inatteignables : leurs hauts faits
        n'étaient décernés nulle part."""
        from forge.rules import achievements, relics

        for relique in relics.CATALOGUE:
            assert relique.achievement in achievements.PAR_CLE, relique.key

    def test_chaque_haut_fait_regarde_un_fait_mesure(self):
        from forge.rules import achievements

        for haut_fait in achievements.CATALOGUE:
            assert haut_fait.fait in achievements.FAITS, haut_fait.key


# --------------------------------------------------------------------------
# Décor
# --------------------------------------------------------------------------

def travailler(user, jour: date, *, xp: int = 40) -> Session:
    return Session.objects.create(
        user=user,
        project=Project.objects.filter(user=user).first(),
        coach_day=jour,
        started_at=datetime(jour.year, jour.month, jour.day, 19, tzinfo=PARIS),
        actual_minutes=25,
        xp_awarded=xp,
        status=Session.DONE,
    )


def _clore_douze_saisons(user, *, today: date = LUNDI) -> dict:
    """Amène la saison en cours au rang douze et la clôt."""
    saison = Season.objects.filter(user=user).order_by("-index").first()
    saison.index = regles.SAISONS_PAR_AN
    saison.save(update_fields=["index"])
    return season_flow.close_season(user, saison, today=today)


def _ouvrir_la_forge(user, *, eclats: int) -> None:
    Ascendance.objects.create(
        user=user, year_index=1, closed_on=LUNDI - timedelta(days=1), voie=regles.FORGE
    )
    user.profile.shards = eclats
    user.profile.save(update_fields=["shards"])


def _compteur(etat: dict, label: str):
    return next(c["value"] for c in etat["compteurs"] if c["label"] == label)


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1, branch="ue5")
    services.open_season(user, starts_on=LUNDI - timedelta(days=30), stake=0)
    return user
