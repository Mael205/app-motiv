"""Tests des sondes et de la détection automatique (SPEC §8, §9, §11.10).

L'invariant surveillé ici est le plus important du sous-système, et le plus
facile à casser sans s'en rendre compte :

> **Une détection marque. Une absence de détection ne certifie rien.**

Un système qui conclurait « rien vu, donc journée tenue » mentirait dans le sens
rassurant. Plusieurs tests existent uniquement pour rendre cette erreur bruyante
si quelqu'un l'écrit un jour.
"""

from datetime import date, timedelta

import pytest

from forge.rules.signals import (
    ADULTE,
    AGENT,
    EXTENSION,
    MIN_MINUTES_TO_MARK,
    MOBILE,
    RESEAUX,
    TRAVAIL_PROJET,
    Signal,
    certifies_held,
    minutes_by_category,
    verdict_for,
)

LUNDI = date(2026, 3, 2)


class TestValidation:
    def test_source_inconnue_refusee(self):
        with pytest.raises(ValueError, match="Source inconnue"):
            Signal(source="webcam", category=RESEAUX, minutes=5, day=LUNDI)

    def test_categorie_inconnue_refusee(self):
        with pytest.raises(ValueError, match="Catégorie inconnue"):
            Signal(source=AGENT, category="pornhub.com", minutes=5, day=LUNDI)

    def test_duree_negative_refusee(self):
        with pytest.raises(ValueError):
            Signal(source=AGENT, category=RESEAUX, minutes=-1, day=LUNDI)

    def test_aucun_champ_ne_transporte_de_contenu(self):
        """Un signal ne sait pas représenter une URL : c'est la garantie."""
        champs = set(Signal.__dataclass_fields__)
        assert champs == {"source", "category", "minutes", "day"}


class TestVerdict:
    def test_assez_de_minutes_marque_la_journee(self):
        signaux = [Signal(source=EXTENSION, category=RESEAUX, minutes=12, day=LUNDI)]
        assert verdict_for(signaux, RESEAUX, LUNDI).marks

    def test_un_passage_bref_ne_marque_pas(self):
        signaux = [Signal(source=EXTENSION, category=RESEAUX, minutes=1, day=LUNDI)]
        assert not verdict_for(signaux, RESEAUX, LUNDI).marks

    def test_le_seuil_est_atteint_par_cumul_de_sources(self):
        signaux = [
            Signal(source=EXTENSION, category=RESEAUX, minutes=2, day=LUNDI),
            Signal(source=MOBILE, category=RESEAUX, minutes=2, day=LUNDI),
        ]
        verdict = verdict_for(signaux, RESEAUX, LUNDI)
        assert verdict.minutes == 4 >= MIN_MINUTES_TO_MARK
        assert verdict.marks and verdict.sources == (EXTENSION, MOBILE)

    def test_une_autre_journee_ne_compte_pas(self):
        signaux = [Signal(source=AGENT, category=ADULTE, minutes=30, day=LUNDI - timedelta(days=1))]
        assert not verdict_for(signaux, ADULTE, LUNDI).marks

    def test_minutes_par_categorie(self):
        signaux = [
            Signal(source=AGENT, category=TRAVAIL_PROJET, minutes=50, day=LUNDI),
            Signal(source=AGENT, category=RESEAUX, minutes=8, day=LUNDI),
        ]
        assert minutes_by_category(signaux, LUNDI) == {TRAVAIL_PROJET: 50, RESEAUX: 8}


class TestAsymetrie:
    """Le silence d'une sonde n'est pas une preuve. Ces tests le verrouillent."""

    def test_aucun_signal_ne_marque_rien_et_ne_certifie_rien(self):
        verdict = verdict_for([], ADULTE, LUNDI)
        assert not verdict.marks
        assert "pas une preuve" in verdict.label

    def test_le_verdict_n_expose_aucun_champ_de_certification(self):
        champs = set(verdict_for([], ADULTE, LUNDI).__dataclass_fields__)
        interdits = {"clean", "held", "verified", "tenue", "certified"}
        assert not (champs & interdits), (
            "aucun champ ne doit pouvoir affirmer qu'une journée a été tenue"
        )

    def test_la_fonction_de_certification_rend_toujours_faux(self):
        assert certifies_held() is False
        assert certifies_held(signals=[], day=LUNDI) is False


@pytest.mark.django_db
class TestIngestionEtMarquage:
    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Garde, Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        Garde.objects.create(user=user, name="Réseaux sociaux", weekly_budget=2, auto_category=RESEAUX)
        Garde.objects.create(user=user, name="Manuelle", weekly_budget=2)
        return user

    def test_un_signal_suffisant_marque_la_garde(self, user):
        from forge import services
        from forge.models import GardeDay

        result = services.ingest_signals(
            user, source=EXTENSION, entries=[{"category": RESEAUX, "minutes": 14}], day=LUNDI
        )
        assert result["stored"] == 1
        assert result["marked"][0]["garde"] == "Réseaux sociaux"
        jour = GardeDay.objects.get(garde__name="Réseaux sociaux", day=LUNDI)
        assert jour.occurred and jour.origin == GardeDay.SONDE

    def test_un_signal_trop_court_ne_marque_pas(self, user):
        from forge import services
        from forge.models import GardeDay

        services.ingest_signals(
            user, source=EXTENSION, entries=[{"category": RESEAUX, "minutes": 1}], day=LUNDI
        )
        assert not GardeDay.objects.filter(day=LUNDI).exists()

    def test_une_garde_sans_categorie_reste_manuelle(self, user):
        from forge import services
        from forge.models import GardeDay

        services.ingest_signals(
            user, source=EXTENSION, entries=[{"category": RESEAUX, "minutes": 30}], day=LUNDI
        )
        assert not GardeDay.objects.filter(garde__name="Manuelle", day=LUNDI).exists()

    def test_une_declaration_manuelle_n_est_jamais_ecrasee(self, user):
        from forge import services
        from forge.models import Garde, GardeDay

        garde = Garde.objects.get(name="Réseaux sociaux")
        services.declare_garde(garde, day=LUNDI, occurred=False)
        services.ingest_signals(
            user, source=EXTENSION, entries=[{"category": RESEAUX, "minutes": 40}], day=LUNDI
        )
        jour = GardeDay.objects.get(garde=garde, day=LUNDI)
        assert not jour.occurred and jour.origin == GardeDay.MAIN

    def test_mais_la_contradiction_est_remontee(self, user):
        """L'utilisateur a le dernier mot ; le désaccord ne disparaît pas pour autant."""
        from forge import services
        from forge.models import Garde

        garde = Garde.objects.get(name="Réseaux sociaux")
        services.declare_garde(garde, day=LUNDI, occurred=False)
        services.ingest_signals(
            user, source=EXTENSION, entries=[{"category": RESEAUX, "minutes": 40}], day=LUNDI
        )
        panel = services.gardes_panel(user, today=LUNDI)
        ligne = next(g for g in panel["gardes"] if g["name"] == "Réseaux sociaux")
        assert ligne["conflict"]
        assert ligne["seen_minutes"] == 40

    def test_aucune_journee_n_est_declaree_tenue_par_une_sonde(self, user):
        """Le cas central : des sondes actives, rien vu, et pourtant rien de déclaré."""
        from forge import services
        from forge.models import GardeDay

        services.ingest_signals(
            user, source=AGENT, entries=[{"category": TRAVAIL_PROJET, "minutes": 90}], day=LUNDI
        )
        assert not GardeDay.objects.filter(day=LUNDI).exists()
        panel = services.gardes_panel(user, today=LUNDI)
        assert panel["to_declare"] == 2

    def test_une_categorie_inconnue_est_refusee_a_l_ingestion(self, user):
        from forge import services

        with pytest.raises(ValueError):
            services.ingest_signals(
                user, source=AGENT, entries=[{"category": "reddit.com/r/x", "minutes": 5}], day=LUNDI
            )
