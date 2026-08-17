"""Garde commune à toute la suite : aucun test ne joint un modèle réel.

``test_coaching`` posait déjà cette garde pour lui-même. Elle remonte ici parce
que le gardien du soir appelle maintenant le modèle (§5.4) : sans ce filet, un
test de déclencheur lancerait le CLI Claude sur la machine de développement —
lentement, en consommant des jetons, et avec un résultat différent à chaque
exécution.

Un test qui veut une réponse la déclare, avec ``set_provider(ScriptedProvider(…))``.
"""

import pytest

from forge.llm import set_provider
from forge.llm.fake import UnavailableProvider


@pytest.fixture(autouse=True)
def sans_modele_reel():
    set_provider(UnavailableProvider())
    yield
    set_provider(None)
