"""Une ligne par semaine, tirée du monde de la saison en cours (§12.2).

## Ce que ce fichier n'est pas

Ce ne sont pas des citations de motivation. Le §5.2 fixe le ton — « zéro
flatterie, zéro bravo champion » — et le §11.10 en fait une règle testée. Une
affiche « tu peux le faire » dans cette application serait la seule phrase qui
ment : le produit ne pense pas que le problème soit la motivation. Le §0.2 dit
l'inverse — trop de motivation, pas trop peu.

Ce sont des lignes du **décor**, dans le registre exact des baselines de
saison, qui existent déjà et qui ont trouvé leur voix : « Le feu ne demande pas
la permission », « Ils passeront par toi », « Le point le plus bas est un point
de départ comme un autre ». Elles nomment la situation, elles ne commentent
jamais celui qui la traverse. C'est la différence entre un décor qui porte et
un poster qui flatte.

## Quatre par saison, et pourquoi quatre

Une saison fait vingt-huit jours, donc quatre semaines. Une ligne par semaine
suit la courbe du mois autant que celle de la saison :

    semaine 1  ce qui s'ouvre
    semaine 2  ce qui s'installe
    semaine 3  le creux — la seule semaine où le mois pèse
    semaine 4  ce qui se ferme

La troisième est écrite en connaissance de cause. Le §0.2 situe l'abandon au
jour cinq ou sept d'un projet ; à l'échelle d'un mois, c'est la troisième
semaine qui use, quand l'ouverture est loin et la fin pas encore en vue.

## Aucun tirage

La ligne se **calcule** depuis la clé de saison et le jour : la même semaine
affiche toujours la même phrase. Un tirage aléatoire ferait de la ligne un
distributeur — on rouvrirait l'application pour voir la suivante, ce qui est
exactement le geste que le §11.1 refuse de récompenser.
"""

from __future__ import annotations

SEMAINES_PAR_SAISON = 4

# Les quatre lignes de chaque saison, dans l'ordre des semaines.
#
# La table couvre la trame courante. Une clé absente — une saison d'archive
# retirée depuis — ne rend rien du tout : mieux vaut pas de ligne qu'une ligne
# empruntée à une autre saison, qui dirait le contraire de son décor.
CITATIONS: dict[str, tuple[str, str, str, str]] = {
    # ---- VOIE DES CIMES : du réveil à l'Empyrée -------------------------
    "eveil": (
        "Tu viens de te réveiller. Ne te rendors pas.",
        "Tu sais maintenant ce qui dormait. Va le chercher.",
        "Personne ne se rendort d'un coup. On se laisse rendormir.",
        "Quatre semaines debout. Garde les yeux ouverts.",
    ),
    "aube_rouge": (
        "Sept levers derrière toi. Vingt et un devant. Avance.",
        "L'aube ne se répète pas, elle recommence. Toi aussi.",
        "Le ciel reste gris plus longtemps cette semaine. Lève-toi quand même.",
        "Compte les levers, pas les intentions. Ils sont à toi.",
    ),
    "porte_ivoire": (
        "Deux portes. Prends celle qui coûte quelque chose.",
        "Le songe et le fait ont la même forme au départ. Choisis le fait.",
        "La mauvaise porte se reconnaît : elle s'ouvre toute seule.",
        "Franchis-la. Ce que tu as fait ce mois-ci ne se rêve plus.",
    ),
    "sanctuaire": (
        "Défends un lieu, pas une humeur.",
        "Les murs tiennent parce que tu les relèves. Relève-les.",
        "Ton créneau est le mur. C'est lui qu'on attaque cette semaine.",
        "Ce que tu défends quatre semaines devient à toi.",
    ),
    "elysion": (
        "Le repos se gagne. Va le gagner.",
        "Les champs ne poussent pas parce que tu les regardes.",
        "Tu vas croire avoir mérité de t'arrêter. Pas encore.",
        "Ce que tu emportes d'ici, c'est toi qui l'as posé.",
    ),
    "ascension": (
        "Personne ne monte par accident. Décide de monter.",
        "La pente ne change pas. Ton pas, si.",
        "Arrête de compter les marches. Monte.",
        "Tu ne redescendras pas ce que tu as monté en quatre semaines.",
    ),
    "valhalla": (
        "La salle est pleine de gens qui ont fini. Fais-toi une place.",
        "On n'entre pas ici pour avoir essayé. Termine.",
        "Une étape finie vaut mieux que trois commencées. Finis-en une.",
        "Ce qui s'assied là a été terminé. Assieds-toi.",
    ),
    "ragnarok": (
        "Tout finit. Bâtis avant.",
        "Le compte à rebours ne se négocie pas. Sers-t'en.",
        "Tout va sembler s'écrouler cette semaine. Fais ta session quand même.",
        "Ce qui reste debout après, c'est ce que tu as fait.",
    ),
    "couronne_solaire": (
        "Ta lumière ne se voit que dans l'ombre. Entre dedans.",
        "Le plus urgent cache le plus important. Écarte l'urgent.",
        "Sept jours sans rien voir venir. C'est là que ça se joue.",
        "Ce qui compte était déjà là au premier jour. Tu le vois maintenant.",
    ),
    "heavens_paradise": (
        "Monte, ou regarde monter. Choisis maintenant.",
        "Une session faite, ou une soirée regardée. Cette semaine tranche.",
        "Il n'y a pas de place assise à mi-hauteur. Continue.",
        "Vingt-huit jours plus haut. Regarde d'où tu viens.",
    ),
    "apotheose": (
        "C'est le mois où tu cesses d'être celui qui essaie.",
        "Rien ne change d'un coup. Tout change en quatre semaines.",
        "L'ancien va revenir frapper cette semaine. N'ouvre pas.",
        "Ce que tu poses jour après jour ne se retire pas.",
    ),
    "empyree": (
        "Plus haut que ce mois-ci, tu n'es jamais allé. Tiens-toi dessus.",
        "Arrivé en haut, la seule direction est de tenir. Tiens.",
        "La hauteur ne protège de rien. Elle t'expose. Reste.",
        "Ce que tu termines ici ne se refera pas à l'identique.",
    ),
    # ---- VOIE DES BRAISES : la chute, le feu, la reforge ----------------
    "chute": (
        "La chute a eu lieu. À toi de décider où elle s'arrête.",
        "Tu ne remonteras pas en niant que tu es tombé. Regarde, puis pousse.",
        "Tu n'as pas encore touché le fond. Une session ce soir, et tu n'iras pas plus bas.",
        "Tu tiens le fond. Prends appui dessus.",
    ),
    "nadir": (
        "Le point le plus bas est un point de départ. C'est le tien.",
        "D'ici, toutes les directions montent. Prends-en une.",
        "Le fond est plat : on s'y tient debout. Repars de là, pas d'ailleurs.",
        "Repars d'où tu es, pas d'où tu aurais voulu être.",
    ),
    "styx": (
        "Une seule traversée, et elle commence ce soir.",
        "L'autre rive ne se voit pas d'ici. Nage quand même.",
        "Le courant paraît plus fort que toi cette semaine. Il ne l'est pas.",
        "Traversé une fois, il n'est plus devant toi. Jamais.",
    ),
    "purgatoire": (
        "Ni en haut ni en bas. Vingt-huit jours pour trancher. Tranche.",
        "L'entre-deux est confortable. C'est tout son danger. Sors.",
        "Tu vas vouloir rester ici cette semaine. Ne reste pas.",
        "On ne sort pas d'ici en attendant. On en sort en marchant.",
    ),
    "solstice_noir": (
        "La nuit la plus longue se travaille. Commence.",
        "L'obscurité ne s'arrête pas parce que tu la regardes. Traverse-la.",
        "Vingt-cinq minutes suffisent à percer une nuit. Pose-les.",
        "Après la plus longue nuit, les jours rallongent. Tu y es.",
    ),
    "cendres": (
        "Ce qui a brûlé fertilise ou stérilise. Décide maintenant.",
        "La cendre ne dit pas ce qu'elle deviendra. Dis-le à sa place.",
        "Sous le gris, quelque chose rougeoie encore. Souffle dessus.",
        "Sème dans ce qui reste. Ne balaie pas.",
    ),
    "hellfest": (
        "Quatre semaines. Le feu ne demande pas la permission, toi non plus.",
        "Tu n'éteindras pas ça en fermant les yeux. Ouvre-les et avance.",
        "À la troisième semaine, le rythme devient une habitude. Ne la lâche pas.",
        "Ce qui traverse le feu ne craint plus la chaleur. Tu traverses.",
    ),
    "inferno": (
        "Ça chauffe à partir de maintenant. Reste dedans.",
        "Descends les cercles un par un. Pas deux.",
        "Le plus chaud est au milieu. Tu y es. Continue.",
        "La sortie est de l'autre côté, jamais en arrière. Marche.",
    ),
    "tonnerre": (
        "Le bruit arrive après. Frappe d'abord.",
        "Ce qui frappe est déjà passé quand tu l'entends. Devance-le.",
        "Le ciel gronde sans tomber cette semaine. Ne t'arrête pas pour ça.",
        "L'écart entre ce que tu prévois et ce que tu fais se réduit. Continue.",
    ),
    "dernier_rempart": (
        "Ils passeront par toi. Tiens la ligne.",
        "Un mur tient par ce que tu remets dessus chaque jour. Remets-en.",
        "C'est la semaine où tu vas sauter une soirée. N'en saute pas deux.",
        "Ce qui n'est pas tombé en vingt-huit jours ne tombera pas ce soir.",
    ),
    "derniere_forge": (
        "Le feu s'éteint à la fin du mois. Pas avant. Frappe.",
        "On ne forge pas à froid. Chauffe d'abord, frappe ensuite.",
        "Le métal résiste le plus cette semaine. Frappe plus fort.",
        "Ce qui sort de la forge a été frappé, pas trouvé. Frappe encore.",
    ),
    "phenix": (
        "Il ne revient pas malgré le feu. Il revient par lui. Toi aussi.",
        "Rien ne renaît sans avoir brûlé entièrement. Laisse brûler.",
        "Ni là où tu étais, ni là où tu vas. Fais ta session quand même.",
        "Ce qui repart n'est pas ce qui était. C'est mieux.",
    ),
}


def semaine_de(jour_index: int) -> int:
    """La semaine de saison, de 1 à 4, depuis le nombre de jours écoulés.

    Bornée aux deux extrémités : un ``jour_index`` négatif — une saison
    engagée mais pas encore commencée, ce que le mode extra du §12.4 produit —
    doit rendre la première semaine, et le vingt-neuvième jour d'une saison
    prolongée la dernière, jamais une cinquième qui n'existe pas.
    """
    return max(1, min(SEMAINES_PAR_SAISON, jour_index // 7 + 1))


def citation_de(key: str, jour_index: int) -> str:
    """La ligne de cette semaine, pour cette saison. Vide si l'on ne sait pas.

    Le vide est un résultat valable et non un repli dégradé : une saison
    d'archive dont la clé a quitté la trame n'a pas de ligne, et lui en prêter
    une empruntée à une autre saison dirait le contraire de son décor.
    """
    lignes = CITATIONS.get(key)
    if not lignes:
        return ""
    return lignes[semaine_de(jour_index) - 1]
