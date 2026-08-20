"""Garde commune à toute la suite : aucun test ne joint un modèle réel.

``test_coaching`` posait déjà cette garde pour lui-même. Elle remonte ici parce
que le gardien du soir appelle maintenant le modèle (§5.4) : sans ce filet, un
test de déclencheur lancerait le CLI Claude sur la machine de développement —
lentement, en consommant des jetons, et avec un résultat différent à chaque
exécution.

Un test qui veut une réponse la déclare, avec ``set_provider(ScriptedProvider(…))``.
"""

import pytest
from django.test.utils import override_settings

from forge.llm import set_provider
from forge.llm.fake import UnavailableProvider


@pytest.fixture(autouse=True, scope="session")
def mots_de_passe_rapides():
    """Hachage bon marché pour la suite, et pour elle seule.

    Django 5 hache les mots de passe en PBKDF2 avec 1,2 million d'itérations —
    c'est exactement ce qu'on veut en production, et c'est mesuré ici à **0,89
    seconde par appel**. Presque chaque test crée un utilisateur dans sa
    fixture, donc la suite passait l'essentiel de son temps à prouver qu'un mot
    de passe de test est bien haché.

    MD5 ici n'affaiblit rien : ce réglage ne sort pas de la session pytest, la
    configuration de production n'est pas touchée, et aucun de ces mots de passe
    n'existe ailleurs que dans une base jetée à la fin du run.
    """
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


@pytest.fixture(autouse=True)
def sans_modele_reel():
    set_provider(UnavailableProvider())
    yield
    set_provider(None)
