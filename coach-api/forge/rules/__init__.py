"""Logique métier pure du coach.

Aucun import Django ici. Ces fonctions prennent des données simples et rendent
des données simples, pour être testables sans base et sans requête HTTP. C'est
là que vivent les règles dont un bug détruirait la confiance dans le système :
le streak, les boucliers, l'XP, les sanctions, la saison.
"""
