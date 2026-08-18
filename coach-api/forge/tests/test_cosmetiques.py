"""Les cartes équipées, et le fait qu'elles changent enfin quelque chose (§12.6).

Le défaut était simple et complet : ``profile.cosmetics`` se remplissait quand
on équipait une carte, la fiche affichait « équipée », et **rien d'autre ne se
passait**. Le champ ne quittait jamais le serveur, aucun écran n'allait le
chercher. Cinq emplacements, cinq récompenses creuses.

Ce fichier vérifie deux choses opposées : que les cosmétiques sortent bien du
serveur, et qu'ils n'entrent dans **aucun** calcul. Le §17 est formel — le loot
est de l'apparence, jamais du pouvoir.
"""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from forge import progression, services
from forge.models import DayWindow, LootCard, Profile, Project, Track
from forge.rules import loot as loot_rules

LUNDI = date(2026, 3, 2)


@pytest.mark.django_db
class TestLesCosmetiques:
    def test_ils_sortent_du_serveur(self, user):
        """Le champ ne quittait jamais la base : c'est tout le défaut."""
        _equiper(user, "theme_eclipse")
        etat = services.home_state(user)
        assert etat["cosmetics"]["theme"]["value"] == "#E85F9F"

    def test_la_valeur_est_resolue_pas_la_cle(self, user):
        """Le client n'a pas le catalogue : lui envoyer une clé l'obligerait à
        dupliquer le contenu de chaque côté."""
        _equiper(user, "emb_couronne")
        resolu = progression.cosmetics(user)
        assert resolu["emblem"]["value"] == "♛"
        assert resolu["emblem"]["label"] == "Couronne"

    def test_un_emplacement_vide_ne_sort_pas(self, user):
        assert progression.cosmetics(user) == {}

    def test_une_carte_retiree_du_catalogue_ne_plante_pas(self, user):
        """Une clé orpheline doit être ignorée, pas faire tomber l'accueil."""
        user.profile.cosmetics = {"theme": "carte_qui_n_existe_plus"}
        user.profile.save(update_fields=["cosmetics"])
        assert progression.cosmetics(user) == {}

    def test_les_cinq_emplacements_se_resolvent(self, user):
        for cle in ("theme_braise", "emb_rune", "cadre_fer", "titre_veilleur", "fin_onde"):
            _equiper(user, cle)
        resolu = progression.cosmetics(user)
        assert set(resolu) == {"theme", "emblem", "frame", "title", "finisher"}


@pytest.mark.django_db
class TestAucunPouvoir:
    """Le §17 : « Le loot est de l'apparence, jamais du pouvoir. »"""

    def test_equiper_ne_change_ni_le_plancher_ni_les_boucliers(self, user):
        avant = (
            services.floor_minutes(user, today=LUNDI),
            services.starting_shields(user, today=LUNDI),
            services.days_off_allowed(user, today=LUNDI),
        )
        for cle in ("theme_eclipse", "emb_couronne", "cadre_aurore", "titre_monarque"):
            _equiper(user, cle)

        apres = (
            services.floor_minutes(user, today=LUNDI),
            services.starting_shields(user, today=LUNDI),
            services.days_off_allowed(user, today=LUNDI),
        )
        assert avant == apres

    def test_aucune_carte_ne_porte_de_valeur_chiffree(self, user):
        """Une carte n'a qu'une charge d'apparence : une couleur, un glyphe, un
        mot. Aucun champ numérique, contrairement aux reliques du §12.8."""
        for carte in loot_rules.CATALOGUE:
            assert not hasattr(carte, "value")
            assert not hasattr(carte, "effect")

    def test_les_cosmetiques_ne_touchent_pas_au_rang(self, user):
        avant = services.rank_state(user, today=LUNDI)
        _equiper(user, "titre_monarque")
        assert services.rank_state(user, today=LUNDI) == avant


def _equiper(user, cle: str) -> None:
    carte = loot_rules.PAR_CLE[cle]
    LootCard.objects.get_or_create(
        user=user, key=cle, defaults={"rarity": carte.rarity, "kind": carte.kind}
    )
    progression.equip_card(user, cle)


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
    services.open_season(user, starts_on=LUNDI - timedelta(days=3), stake=0)
    return user
